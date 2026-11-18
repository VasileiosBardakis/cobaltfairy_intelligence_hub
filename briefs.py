import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).parent
DB = ROOT / "data" / "intel.db"
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
PROMPT_VERSION = "brief-v1"

TREND_WORDS = {
    "trend", "trends", "trending", "growing", "growth", "increasing",
    "rising", "declining", "declined", "shift", "shifting", "momentum",
    "recurring",
}
COEXIST_WORDS = {
    "remains", "remain", "still", "coexists", "coexist",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
    brief_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    positioning TEXT NOT NULL,
    checker_status TEXT NOT NULL,
    checker_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    brief_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,
    quote TEXT,
    verification_status TEXT NOT NULL,
    checker_note TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_brief ON claims(brief_id);
"""

SYSTEM_PROMPT = """You write a short market-intelligence positioning brief.
Use only the supplied signal and evidence. Do not use outside knowledge.
Return JSON only:
{
  "positioning": "2-4 sentences",
  "claims": [
    {
      "claim": "short claim",
      "evidence_ids": ["evidence-id"],
      "quote": "exact text copied from one cited evidence quote"
    }
  ]
}
Rules:
- Every claim must cite at least one supplied evidence_id.
- If you provide a quote, it must be copied exactly from a cited evidence quote.
- Claims without a quote are inferential.
- If the signal status is insufficient, state that evidence is limited and do not use trend, pattern, growth, shift or recurring language.
- If evidence includes a pricing_rename, the old and new names are the same plan over time. Never say the old plan remains, coexists, or is a separate current plan.
- Keep the positioning to at most 80 words.
"""


def _hash(prefix, *parts):
    raw = "|".join([prefix, *[str(part) for part in parts]])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _norm(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _parse(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def _input_hash(signal, evidence):
    fields = [
        "signal_id", "signal_type", "title", "entity", "period_start",
        "period_end", "summary", "status", "confidence", "coverage_note",
        "rule_version",
    ]
    payload = {
        "signal": {key: signal.get(key) for key in fields},
        "evidence": evidence,
    }
    return _hash("brief-input", json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _call(client, signal, evidence):
    signal_fields = [
        "signal_id", "signal_type", "title", "entity", "period_start",
        "period_end", "summary", "status", "coverage_note",
    ]
    payload = {
        "signal": {key: signal.get(key) for key in signal_fields},
        "evidence": [
            {
                "evidence_id": item["evidence_id"],
                "evidence_type": item["evidence_type"],
                "quote": item["quote"],
            }
            for item in evidence
        ],
    }
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )
    return _parse(response.choices[0].message.content)


def _has_trend(text):
    text = _norm(text).replace("growing business", "")
    tokens = set(re.findall(r"[a-z]+", text))
    return bool(tokens & TREND_WORDS)


def _rename_context(evidence):
    names = set()
    for item in evidence:
        if item["evidence_type"] != "pricing_rename":
            continue
        match = re.search(
            r"plan renamed from (.+?) to .+?;", _norm(item["quote"])
        )
        if match:
            names.add(match.group(1).strip())
    return names


def _rename_issue(text, renamed_from):
    if not renamed_from:
        return False
    text = _norm(text)
    tokens = set(re.findall(r"[a-z]+", text))
    mentions_old = any(name in text for name in renamed_from)
    qualified = tokens & {
        "baseline", "former", "formerly", "previous", "previously",
        "renamed", "was", "old",
    }
    qualified_phrases = (
        "now named", "now called", "renamed to", "name changed to",
        "formerly known as", "previously known as",
    )
    renamed = bool(qualified) or any(phrase in text for phrase in qualified_phrases)
    return (mentions_old and not renamed) or bool(tokens & COEXIST_WORDS)


def check_output(output, signal, evidence):
    by_id = {item["evidence_id"]: item["quote"] for item in evidence}
    renamed_from = _rename_context(evidence)
    insufficient = (
        signal["status"] == "insufficient"
        and signal["signal_type"] in {"social_theme", "cross_source"}
    )

    claims = []
    for item in output.get("claims") or []:
        claim = str(item.get("claim") or "").strip()
        ids = [str(value) for value in (item.get("evidence_ids") or []) if str(value).strip()]
        quote = str(item.get("quote") or "").strip()
        status, note = "verified", ""

        if not claim:
            status, note = "unsupported", "empty claim"
        elif not ids:
            status, note = "unsupported", "missing evidence id"
        elif any(evidence_id not in by_id for evidence_id in ids):
            status, note = "unsupported", "unknown evidence id"
        elif quote and not any(
            _norm(quote) in _norm(by_id[evidence_id]) for evidence_id in ids
        ):
            status, note = "unsupported", "quote not found in cited evidence"
        elif not quote:
            status, note = "inferential", "no exact quote"

        if insufficient and _has_trend(claim):
            status, note = "unsupported", "trend language with insufficient evidence"
        if _rename_issue(claim, renamed_from):
            status, note = "unsupported", "treats a renamed plan as a current separate plan"

        claims.append({
            "claim_text": claim,
            "evidence_ids": ids,
            "quote": quote or None,
            "verification_status": status,
            "checker_note": note,
        })

    positioning = str(output.get("positioning") or "")
    if _rename_issue(positioning, renamed_from):
        return claims, "needs_review", (
            "positioning treats a renamed plan as a current separate plan"
        )
    return claims, "auto_checked", ""


def generate_briefs(db_path=DB, force=False, client=None):
    if client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("DEEPSEEK_API_KEY is not set; no briefs written.")
            return 1
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    signals = pd.read_sql_query("SELECT * FROM signals ORDER BY signal_id", con)
    signal_ids = tuple(signals["signal_id"])
    if signal_ids:
        placeholders = ",".join("?" * len(signal_ids))
        con.execute(
            f"DELETE FROM claims WHERE signal_id NOT IN ({placeholders})", signal_ids
        )
        con.execute(
            f"DELETE FROM briefs WHERE signal_id NOT IN ({placeholders})", signal_ids
        )
    else:
        con.execute("DELETE FROM claims")
        con.execute("DELETE FROM briefs")
    con.commit()

    created = 0
    for signal in signals.to_dict("records"):
        evidence = pd.read_sql_query(
            "SELECT evidence_id, evidence_type, quote FROM signal_evidence "
            "WHERE signal_id=? ORDER BY evidence_id",
            con,
            params=[signal["signal_id"]],
        ).to_dict("records")
        if not evidence:
            print(f"{signal['signal_id']}: no evidence, skipped")
            continue

        input_hash = _input_hash(signal, evidence)
        brief_id = _hash("brief", signal["signal_id"], MODEL, PROMPT_VERSION)
        existing = con.execute(
            "SELECT input_hash FROM briefs WHERE brief_id=?", (brief_id,)
        ).fetchone()
        if existing and existing[0] == input_hash and not force:
            continue

        output = _call(client, signal, evidence)
        claims, checker_status, checker_note = check_output(output, signal, evidence)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute("DELETE FROM claims WHERE brief_id=?", (brief_id,))
        con.execute(
            """
            INSERT OR REPLACE INTO briefs (
                brief_id, signal_id, model, prompt_version, input_hash,
                positioning, checker_status, checker_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brief_id, signal["signal_id"], MODEL, PROMPT_VERSION,
                input_hash, str(output.get("positioning") or "").strip(),
                checker_status, checker_note, created_at,
            ),
        )
        for index, claim in enumerate(claims, 1):
            claim_id = _hash(
                "claim", brief_id, index, claim["claim_text"]
            )
            con.execute(
                """
                INSERT OR REPLACE INTO claims (
                    claim_id, brief_id, signal_id, claim_text, evidence_ids,
                    quote, verification_status, checker_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id, brief_id, signal["signal_id"], claim["claim_text"],
                    json.dumps(claim["evidence_ids"]), claim["quote"],
                    claim["verification_status"], claim["checker_note"], created_at,
                ),
            )
        con.commit()
        created += 1
        print(f"{signal['signal_id']}: {len(claims)} claims")

    print("briefs created:", created)
    print(
        "claims:",
        con.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
    )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(generate_briefs())
