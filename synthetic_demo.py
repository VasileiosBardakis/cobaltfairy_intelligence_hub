import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "synthetic_social"
POSTS_PATH = FIXTURE / "social_posts_synthetic.csv"
COVERAGE_PATH = FIXTURE / "social_coverage_synthetic.csv"
MIN_POSTS = 3
CREATED_AT = "2026-11-18T00:00:00+00:00"

CORE_THEMES = {
    "ai_automation",
    "peak_season_bfcm",
    "email_sms_multichannel",
    "customer_data_personalization",
    "discount_promotion",
    "product_positioning",
}

THEME_LABELS = {
    "ai_automation": "AI and automation",
    "peak_season_bfcm": "Peak season and BFCM",
    "email_sms_multichannel": "Email and SMS multichannel",
    "customer_data_personalization": "Customer data and personalization",
    "discount_promotion": "Discount and promotion",
    "community_events": "Community and events",
    "brand_creative": "Brand and creative",
    "product_positioning": "Product positioning",
}

SYNTHETIC_PRICING = {
    "AlphaMail": {
        "plan": "Pro",
        "baseline": 19,
        "current": 24,
        "tier": "5,000 contacts",
        "comparable": True,
    },
    "BetaSend": {
        "plan": "Growth",
        "baseline": 29,
        "current": 35,
        "tier": "10,000 contacts",
        "comparable": True,
    },
    "GammaMail": {
        "plan": "Business",
        "baseline": 49,
        "current": 49,
        "tier": "seat-based to contact-based",
        "comparable": False,
    },
}

SIGNAL_COLUMNS = [
    "signal_id", "signal_type", "title", "entity", "period_start",
    "period_end", "summary", "status", "confidence", "rule_version",
    "coverage_note", "created_at",
]
EVIDENCE_COLUMNS = [
    "signal_id", "evidence_id", "evidence_type", "quote", "role", "verified",
]
BRIEF_COLUMNS = [
    "brief_id", "signal_id", "model", "prompt_version", "input_hash",
    "positioning", "checker_status", "checker_note", "created_at",
]
CLAIM_COLUMNS = [
    "claim_id", "brief_id", "signal_id", "claim_text", "evidence_ids",
    "quote", "verification_status", "checker_note", "created_at",
]
THEME_LABEL_COLUMNS = [
    "post_id", "taxonomy_id", "version", "theme_id", "confidence",
    "evidence_quote", "is_new_theme", "label_source", "model",
    "prompt_version", "created_at",
]


def _id(prefix, key):
    raw = f"{prefix}|{key}".encode("utf-8")
    return "syn-" + hashlib.sha1(raw).hexdigest()[:16]


def load_fixture():
    posts = pd.read_csv(POSTS_PATH, dtype=str, keep_default_na=False)
    coverage = pd.read_csv(COVERAGE_PATH, dtype=str, keep_default_na=False)
    coverage["posts_captured"] = pd.to_numeric(
        coverage["posts_captured"], errors="coerce"
    ).astype("Int64")
    return posts, coverage


def build_demo():
    posts, coverage = load_fixture()
    signals = []
    evidence = []
    briefs = []
    claims = []
    theme_labels = []

    for theme, group in posts.groupby("synthetic_theme", sort=True):
        label = THEME_LABELS.get(theme, theme)
        n = len(group)
        brands = sorted(group["brand"].unique())
        status = "candidate" if n >= MIN_POSTS else "insufficient"
        confidence = 0.9 if theme in CORE_THEMES else 0.65
        signal_id = _id("social", theme)
        brief_id = _id("brief", theme)

        signals.append(
            {
                "signal_id": signal_id,
                "signal_type": "social_theme",
                "title": f"{label}: {n} synthetic posts",
                "entity": theme,
                "period_start": group["posted_at"].min(),
                "period_end": group["posted_at"].max(),
                "summary": (
                    f"Synthetic demo: {n} posts across {len(brands)} fictional "
                    "brand(s). Not real evidence."
                ),
                "status": status,
                "confidence": confidence,
                "rule_version": "synthetic-fixture-v1",
                "coverage_note": (
                    "Synthetic fixture; fictional brands/posts; not real evidence. "
                    "Facebook, Instagram, LinkedIn; 2026-08-18 to 2026-11-18."
                ),
                "created_at": CREATED_AT,
            }
        )

        for row in group.sort_values("posted_at").to_dict("records"):
            evidence.append(
                {
                    "signal_id": signal_id,
                    "evidence_id": f"syn:{row['post_id']}",
                    "evidence_type": "synthetic_social_post",
                    "quote": row["text"],
                    "role": "supporting",
                    "verified": 1,
                }
            )
            theme_labels.append(
                {
                    "post_id": row["post_id"],
                    "taxonomy_id": "social_competitive",
                    "version": "1",
                    "theme_id": theme,
                    "confidence": confidence,
                    "evidence_quote": row["text"],
                    "is_new_theme": False,
                    "label_source": "synthetic_fixture",
                    "model": "synthetic_fixture",
                    "prompt_version": "synthetic-demo-v1",
                    "created_at": CREATED_AT,
                }
            )

        briefs.append(
            {
                "brief_id": brief_id,
                "signal_id": signal_id,
                "model": "synthetic_fixture",
                "prompt_version": "synthetic-demo-v1",
                "input_hash": _id("input", theme),
                "positioning": (
                    f"Synthetic demo only. {label} appears in {n} fictional "
                    f"posts across {len(brands)} brands. This fixture exercises "
                    "the pipeline; it is not competitor evidence."
                ),
                "checker_status": "fixture",
                "checker_note": "Synthetic fixture; no AI call.",
                "created_at": CREATED_AT,
            }
        )

        for row in group.sort_values("posted_at").tail(3).to_dict("records"):
            claim_id = _id("claim", f"{theme}:{row['post_id']}")
            claims.append(
                {
                    "claim_id": claim_id,
                    "brief_id": brief_id,
                    "signal_id": signal_id,
                    "claim_text": f"{row['brand']} post covers {label}.",
                    "evidence_ids": json.dumps([f"syn:{row['post_id']}"]),
                    "quote": row["text"],
                    "verification_status": "verified",
                    "checker_note": "Synthetic fixture quote.",
                    "created_at": CREATED_AT,
                }
            )

    for brand, pricing in SYNTHETIC_PRICING.items():
        brand_posts = posts[posts["brand"] == brand]
        if brand_posts.empty:
            continue
        counts = brand_posts.groupby("synthetic_theme").size().sort_values(
            ascending=False
        )
        top_themes = list(counts[counts >= MIN_POSTS].index[:2])
        top_labels = [THEME_LABELS.get(theme, theme) for theme in top_themes]
        social_rows = (
            brand_posts[brand_posts["synthetic_theme"].isin(top_themes)]
            .sort_values("posted_at")
            .tail(3)
            .to_dict("records")
        )
        if not social_rows:
            social_rows = (
                brand_posts.sort_values("posted_at").tail(3).to_dict("records")
            )

        signal_id = _id("cross", brand)
        brief_id = _id("brief-cross", brand)
        price_evidence_id = f"synpricing:{brand}:{pricing['plan']}"
        comparable = pricing["comparable"]
        change_pct = (
            (pricing["current"] - pricing["baseline"]) / pricing["baseline"] * 100
            if pricing["baseline"]
            else 0
        )
        if comparable:
            price_quote = (
                f"{brand} {pricing['plan']}: ${pricing['baseline']} -> "
                f"${pricing['current']}/month for {pricing['tier']} "
                f"({change_pct:+.1f}%); synthetic fixture."
            )
            summary = (
                f"Synthetic pricing change on {pricing['plan']} "
                f"(${pricing['baseline']} -> ${pricing['current']}, "
                f"{change_pct:+.1f}%) co-occurs with "
                f"{', '.join(top_labels)}. Co-occurrence only; no causal link."
            )
            status = "inferential"
            confidence = 0.7
            positioning = (
                f"Synthetic demo only. {brand} changed {pricing['plan']} pricing "
                f"(${pricing['baseline']} -> ${pricing['current']}, "
                f"{change_pct:+.1f}%) while its posts emphasize "
                f"{', '.join(top_labels)}. Co-occurrence only; no causal link."
            )
        else:
            price_quote = (
                f"{brand} {pricing['plan']}: ${pricing['current']}/month; "
                f"pricing basis changed to {pricing['tier']}; synthetic fixture."
            )
            summary = (
                f"Synthetic pricing basis changed for {pricing['plan']}; "
                "no like-for-like price comparison. Co-occurrence with "
                f"{', '.join(top_labels)} is not established."
            )
            status = "insufficient"
            confidence = 0.4
            positioning = (
                f"Synthetic demo only. {brand} changed its pricing basis for "
                f"{pricing['plan']}; no like-for-like comparison. Co-occurrence "
                f"with {', '.join(top_labels)} is not established."
            )

        signals.append(
            {
                "signal_id": signal_id,
                "signal_type": "cross_source",
                "title": f"{brand}: synthetic pricing and social messaging",
                "entity": brand,
                "period_start": brand_posts["posted_at"].min(),
                "period_end": brand_posts["posted_at"].max(),
                "summary": summary,
                "status": status,
                "confidence": confidence,
                "rule_version": "synthetic-fixture-v1",
                "coverage_note": (
                    "Synthetic fixture; fictional brand and synthetic pricing; "
                    "not real evidence. Co-occurrence only; no causal link."
                ),
                "created_at": CREATED_AT,
            }
        )

        for row in social_rows:
            evidence.append(
                {
                    "signal_id": signal_id,
                    "evidence_id": f"syn:{row['post_id']}",
                    "evidence_type": "synthetic_social_post",
                    "quote": row["text"],
                    "role": "supporting",
                    "verified": 1,
                }
            )
        evidence.append(
            {
                "signal_id": signal_id,
                "evidence_id": price_evidence_id,
                "evidence_type": "synthetic_pricing",
                "quote": price_quote,
                "role": "supporting",
                "verified": 1,
            }
        )

        briefs.append(
            {
                "brief_id": brief_id,
                "signal_id": signal_id,
                "model": "synthetic_fixture",
                "prompt_version": "synthetic-demo-v1",
                "input_hash": _id("input-cross", brand),
                "positioning": positioning,
                "checker_status": "fixture",
                "checker_note": "Synthetic fixture; no AI call.",
                "created_at": CREATED_AT,
            }
        )

        if social_rows and top_labels:
            claims.append(
                {
                    "claim_id": _id("claim-cross", f"{brand}:social"),
                    "brief_id": brief_id,
                    "signal_id": signal_id,
                    "claim_text": (
                        f"{brand} posts emphasize {top_labels[0]}."
                    ),
                    "evidence_ids": json.dumps(
                        [f"syn:{social_rows[-1]['post_id']}"]
                    ),
                    "quote": social_rows[-1]["text"],
                    "verification_status": "verified",
                    "checker_note": "Synthetic fixture quote.",
                    "created_at": CREATED_AT,
                }
            )

        price_claim_text = (
            f"{brand} {pricing['plan']} price changed from "
            f"${pricing['baseline']} to ${pricing['current']}."
            if comparable
            else f"{brand} {pricing['plan']} pricing basis changed."
        )
        claims.append(
            {
                "claim_id": _id("claim-cross", f"{brand}:price"),
                "brief_id": brief_id,
                "signal_id": signal_id,
                "claim_text": price_claim_text,
                "evidence_ids": json.dumps([price_evidence_id]),
                "quote": price_quote,
                "verification_status": "verified",
                "checker_note": "Synthetic fixture quote.",
                "created_at": CREATED_AT,
            }
        )

        claims.append(
            {
                "claim_id": _id("claim-cross", f"{brand}:inference"),
                "brief_id": brief_id,
                "signal_id": signal_id,
                "claim_text": (
                    f"{brand} may be pairing the pricing change with a "
                    "value message."
                ),
                "evidence_ids": json.dumps(
                    [price_evidence_id]
                    + [f"syn:{row['post_id']}" for row in social_rows]
                ),
                "quote": None,
                "verification_status": "inferential",
                "checker_note": "no exact quote",
                "created_at": CREATED_AT,
            }
        )

        if brand in {"AlphaMail", "GammaMail"}:
            bad_claim = (
                f"{brand} is gaining market share because of the price change."
                if brand == "AlphaMail"
                else f"{brand} is shifting upmarket."
            )
            claims.append(
                {
                    "claim_id": _id("claim-cross", f"{brand}:unsupported"),
                    "brief_id": brief_id,
                    "signal_id": signal_id,
                    "claim_text": bad_claim,
                    "evidence_ids": json.dumps([price_evidence_id]),
                    "quote": bad_claim,
                    "verification_status": "unsupported",
                    "checker_note": (
                        "synthetic error case: claim not supported by cited "
                        "evidence"
                    ),
                    "created_at": CREATED_AT,
                }
            )

    return {
        "social": posts,
        "coverage": coverage,
        "signals": pd.DataFrame(signals, columns=SIGNAL_COLUMNS),
        "evidence": pd.DataFrame(evidence, columns=EVIDENCE_COLUMNS),
        "briefs": pd.DataFrame(briefs, columns=BRIEF_COLUMNS),
        "claims": pd.DataFrame(claims, columns=CLAIM_COLUMNS),
        "theme_labels": pd.DataFrame(theme_labels, columns=THEME_LABEL_COLUMNS),
    }
