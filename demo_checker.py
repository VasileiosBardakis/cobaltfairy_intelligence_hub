"""Demonstrate the brief checker accepting and rejecting AI output.

Read-only: loads real signals and evidence from data/intel.db and runs
crafted brief outputs through briefs.check_output. No API calls, no
database writes.

Run:
    .\\.venv\\Scripts\\python.exe demo_checker.py
"""

import sqlite3
from pathlib import Path

import briefs

ROOT = Path(__file__).parent
DB = ROOT / "data" / "intel.db"

PRICE_SIGNAL = "MailerLite changes Power price at 500 subscribers"
WEAK_SIGNAL = "MailerLite: pricing and social messaging"

PRICE_CURRENT = "pricing:MailerLite:Power:500:subscribers"
PRICE_BASELINE = "pricing_baseline:MailerLite:Advanced:500"
SOCIAL_POST = "social:fb-mailerlite-2026-11-17-1"


def load_signal(con, title):
    con.row_factory = sqlite3.Row
    signal = con.execute(
        "SELECT * FROM signals WHERE title=?", (title,)
    ).fetchone()
    if signal is None:
        raise SystemExit(f"Signal not found: {title}")
    evidence = [
        dict(row)
        for row in con.execute(
            "SELECT evidence_id, evidence_type, quote FROM signal_evidence "
            "WHERE signal_id=? ORDER BY evidence_type, evidence_id",
            (signal["signal_id"],),
        )
    ]
    return dict(signal), evidence


def quote_for(evidence, evidence_id):
    for item in evidence:
        if item["evidence_id"] == evidence_id:
            return item["quote"]
    raise SystemExit(f"Evidence not found: {evidence_id}")


def claim(claim_text, evidence_ids, quote=""):
    return {
        "claim": claim_text,
        "evidence_ids": evidence_ids,
        "quote": quote,
    }


def run_case(label, signal, evidence, output, expected_claim,
             expected_brief="auto_checked"):
    claims, brief_status, brief_note = briefs.check_output(
        output, signal, evidence
    )
    actual_claim = claims[0]["verification_status"] if claims else "-"
    actual_note = (claims[0]["checker_note"] if claims else "") or brief_note
    passed = actual_claim == expected_claim and brief_status == expected_brief
    print(f"{'PASS' if passed else 'FAIL'}  {label}")
    print(f"      claim status: {actual_claim:<11} brief status: {brief_status}")
    if actual_note:
        print(f"      reason: {actual_note}")
    print()
    return passed


def main():
    if not DB.exists():
        raise SystemExit(f"Database not found at {DB}; run ingest.py first.")

    con = sqlite3.connect(DB)
    try:
        price_signal, price_evidence = load_signal(con, PRICE_SIGNAL)
        weak_signal, weak_evidence = load_signal(con, WEAK_SIGNAL)
        weak_signal = dict(weak_signal)
        weak_signal["status"] = "insufficient"
        weak_signal["signal_type"] = "cross_source"
    finally:
        con.close()

    power_quote = quote_for(price_evidence, PRICE_CURRENT)
    baseline_quote = quote_for(price_evidence, PRICE_BASELINE)
    social_quote = quote_for(weak_evidence, SOCIAL_POST)

    print("Brief checker demonstration")
    print("=" * 72)
    print(f"Real price signal:  {price_signal['title']} "
          f"({price_signal['status']})")
    print(f"Weak social signal: {weak_signal['title']} "
          f"({weak_signal['status']}, demo override)")
    print("=" * 72)
    print()

    results = []

    results.append(run_case(
        "Good claim with an exact quote",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite raised Power from $20 to $25.",
            "claims": [claim(
                "MailerLite raised Power from $20 to $25 at 500 subscribers.",
                [PRICE_BASELINE, PRICE_CURRENT],
                "$25/month at 500 subscribers",
            )],
        },
        "verified",
    ))

    results.append(run_case(
        "Claim with no exact quote",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite raised Power.",
            "claims": [claim(
                "MailerLite raised the Power price.",
                [PRICE_CURRENT],
                "",
            )],
        },
        "inferential",
    ))

    results.append(run_case(
        "Invented quote is rejected",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite cut Power.",
            "claims": [claim(
                "MailerLite cut Power to $10 per month.",
                [PRICE_CURRENT],
                "Power is free now.",
            )],
        },
        "unsupported",
    ))

    results.append(run_case(
        "Unknown evidence id is rejected",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite raised Power.",
            "claims": [claim(
                "MailerLite raised Power.",
                [PRICE_CURRENT, "made:up:evidence"],
                power_quote,
            )],
        },
        "unsupported",
    ))

    results.append(run_case(
        "Renamed plan treated as still available is rejected",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite raised Power.",
            "claims": [claim(
                "The Advanced plan remains available at $20 per month.",
                [PRICE_BASELINE],
                baseline_quote,
            )],
        },
        "unsupported",
    ))

    results.append(run_case(
        "Baseline-qualified old plan name is allowed",
        price_signal, price_evidence,
        {
            "positioning": "MailerLite raised Power.",
            "claims": [claim(
                "The baseline Advanced plan was $20 per month.",
                [PRICE_BASELINE],
                baseline_quote,
            )],
        },
        "verified",
    ))

    results.append(run_case(
        "Trend language under insufficient evidence is rejected",
        weak_signal, weak_evidence,
        {
            "positioning": "MailerLite messaging is changing.",
            "claims": [claim(
                "Discount messaging is growing across competitors.",
                [SOCIAL_POST],
                social_quote,
            )],
        },
        "unsupported",
    ))

    results.append(run_case(
        "Positioning that resurrects a renamed plan needs review",
        price_signal, price_evidence,
        {
            "positioning": (
                "Power is higher priced while Advanced remains available."
            ),
            "claims": [],
        },
        "-",
        expected_brief="needs_review",
    ))

    passed = sum(results)
    print(f"{passed}/{len(results)} cases matched expectations")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
