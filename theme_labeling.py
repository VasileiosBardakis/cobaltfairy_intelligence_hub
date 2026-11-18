import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).parent
TAXONOMY = ROOT / "data" / "theme_taxonomy.csv"
SOCIAL_POSTS = ROOT / "data" / "social_posts.csv"
THEME_LABELS = ROOT / "data" / "theme_labels.csv"

TAXONOMY_ID = "social_competitive"
TAXONOMY_VERSION = "1"
PROMPT_VERSION = "theme-label-v1"
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

TAXONOMY_COLUMNS = [
    "taxonomy_id", "version", "theme_id", "label", "description",
    "include_examples", "exclude_examples", "active", "source",
]
LABEL_COLUMNS = [
    "post_id", "taxonomy_id", "version", "theme_id", "confidence",
    "evidence_quote", "is_new_theme", "label_source", "model",
    "prompt_version", "created_at",
]

SYSTEM_PROMPT = """You label social posts with a fixed taxonomy.
Return JSON only with this shape:
{
  "labels": [
    {"theme_id": "existing_theme_id", "confidence": 0.0, "evidence_quote": "exact text from the post"}
  ],
  "new_themes": [
    {"theme_id": "new_snake_case_id", "label": "Short label", "description": "What it covers", "include_examples": "examples", "exclude_examples": "examples"}
  ]
}
Rules:
- Use existing theme_ids whenever they fit.
- If no existing theme fits, create a new theme and reference it in labels.
- Every label must include an exact quote copied from the post. Never invent a quote.
- Confidence must be between 0 and 1.
- Do not use outside knowledge about the company.
"""


def _effective_taxonomy(taxonomy, taxonomy_id):
    taxonomy = taxonomy[taxonomy["active"].str.lower() == "true"]
    base = taxonomy[taxonomy["taxonomy_id"] == "base"]
    overrides = taxonomy[taxonomy["taxonomy_id"] == taxonomy_id]
    return pd.concat([base, overrides], ignore_index=True).drop_duplicates(
        "theme_id", keep="last"
    ).reset_index(drop=True)


def load_taxonomy(path=TAXONOMY, taxonomy_id=TAXONOMY_ID):
    taxonomy = pd.read_csv(path, dtype=str, keep_default_na=False)
    return _effective_taxonomy(taxonomy, taxonomy_id)


def normalize(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def validate_output(output, post_text, themes):
    known = set(themes["theme_id"])
    raw_new = output.get("new_themes") or []
    raw_labels = output.get("labels") or []
    warnings = []
    new_by_id = {}

    for item in raw_new:
        label = str(item.get("label") or "").strip()
        if not label:
            warnings.append("new theme without label")
            continue
        raw_id = str(item.get("theme_id") or slugify(label))
        theme_id = slugify(raw_id)
        if not theme_id:
            warnings.append(f"invalid new theme id for {label!r}")
            continue
        if theme_id in known:
            continue
        new_by_id[theme_id] = {
            "theme_id": theme_id,
            "label": label,
            "description": str(item.get("description") or label),
            "include_examples": str(item.get("include_examples") or ""),
            "exclude_examples": str(item.get("exclude_examples") or ""),
        }
        known.add(theme_id)

    labels = []
    for item in raw_labels:
        theme_id = slugify(item.get("theme_id") or "")
        if theme_id not in known:
            warnings.append(f"unknown theme dropped: {theme_id or '<empty>'}")
            continue
        quote = str(item.get("evidence_quote") or "").strip()
        if not quote or normalize(quote) not in normalize(post_text):
            warnings.append(f"quote mismatch dropped: {theme_id}")
            continue
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            warnings.append(f"invalid confidence dropped: {theme_id}")
            continue
        if not 0 <= confidence <= 1:
            warnings.append(f"confidence out of range dropped: {theme_id}")
            continue
        labels.append({
            "theme_id": theme_id,
            "confidence": confidence,
            "evidence_quote": quote,
            "is_new_theme": theme_id in new_by_id,
        })

    referenced = {label["theme_id"] for label in labels}
    new_themes = [theme for theme_id, theme in new_by_id.items() if theme_id in referenced]
    return labels, new_themes, warnings


def label_post(client, post_text, themes, model=MODEL):
    taxonomy = themes[[
        "theme_id", "label", "description", "include_examples", "exclude_examples",
    ]].to_dict("records")
    user = json.dumps({"taxonomy": taxonomy, "post_text": post_text}, ensure_ascii=False)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )
    return parse_json(response.choices[0].message.content)


def add_new_themes(taxonomy, new_themes, taxonomy_id=TAXONOMY_ID):
    if not new_themes:
        return taxonomy
    rows = pd.DataFrame([
        {
            "taxonomy_id": taxonomy_id,
            "version": TAXONOMY_VERSION,
            "theme_id": theme["theme_id"],
            "label": theme["label"],
            "description": theme["description"],
            "include_examples": theme["include_examples"],
            "exclude_examples": theme["exclude_examples"],
            "active": "true",
            "source": "llm",
        }
        for theme in new_themes
    ])
    return pd.concat([taxonomy, rows[TAXONOMY_COLUMNS]], ignore_index=True)


def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is not set; no labels written.")
        return 1

    posts = pd.read_csv(SOCIAL_POSTS, dtype=str, keep_default_na=False)
    taxonomy_all = pd.read_csv(TAXONOMY, dtype=str, keep_default_na=False)
    themes = _effective_taxonomy(taxonomy_all, TAXONOMY_ID)
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    rows = []
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for post in posts.itertuples(index=False):
        output = label_post(client, post.text, themes)
        labels, new_themes, warnings = validate_output(output, post.text, themes)
        for warning in warnings:
            print(f"{post.post_id}: {warning}")
        if new_themes:
            taxonomy_all = add_new_themes(taxonomy_all, new_themes)
            themes = _effective_taxonomy(taxonomy_all, TAXONOMY_ID)
        for label in labels:
            rows.append({
                "post_id": post.post_id,
                "taxonomy_id": TAXONOMY_ID,
                "version": TAXONOMY_VERSION,
                "theme_id": label["theme_id"],
                "confidence": label["confidence"],
                "evidence_quote": label["evidence_quote"],
                "is_new_theme": label["is_new_theme"],
                "label_source": "llm",
                "model": MODEL,
                "prompt_version": PROMPT_VERSION,
                "created_at": created_at,
            })
        print(f"{post.post_id}: {len(labels)} labels")

    taxonomy_all.to_csv(TAXONOMY, index=False)
    pd.DataFrame(rows, columns=LABEL_COLUMNS).to_csv(THEME_LABELS, index=False)
    print(f"wrote {len(rows)} labels to {THEME_LABELS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
