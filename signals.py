import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import analysis
import pricing

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "intel.db"

MIN_CONFIDENCE = 0.5
MIN_POSTS = 3
RULE_SOCIAL = "social-theme-v1"
RULE_PRICING = "pricing-diff-v1"
RULE_CF = "cf-market-v1"
RULE_CROSS = "cross-source-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    signal_type TEXT NOT NULL,
    title TEXT NOT NULL,
    entity TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    rule_version TEXT NOT NULL,
    coverage_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signal_evidence (
    signal_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    quote TEXT,
    role TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (signal_id, evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_signals_type_status
    ON signals(signal_type, status);
"""


def _csv(name):
    return pd.read_csv(DATA / name, dtype=str, keep_default_na=False)


def _ev(evidence_id, evidence_type, quote):
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "quote": quote,
        "role": "supporting",
    }


def _first(frame, **eq):
    for column, value in eq.items():
        frame = frame[frame[column] == value]
        if frame.empty:
            return None
    return frame.iloc[0].to_dict()


def _id(signal_type, key, start, end, rule):
    raw = "|".join([signal_type, key, str(start), str(end), rule])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _add(store, signal_type, key, title, entity, start, end, summary,
         status, confidence, rule, note, evidence):
    signal_id = _id(signal_type, key, start, end, rule)
    signal = store.setdefault(signal_id, {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "title": title,
        "entity": entity,
        "period_start": start,
        "period_end": end,
        "summary": summary,
        "status": status,
        "confidence": confidence,
        "rule_version": rule,
        "coverage_note": note,
        "evidence": [],
    })
    seen = {item["evidence_id"] for item in signal["evidence"]}
    signal["evidence"].extend(
        item for item in evidence if item["evidence_id"] not in seen
    )


def _social_evidence(rows):
    return [
        _ev(f"social:{row['post_id']}", "social_post", row["evidence_quote"])
        for row in rows.drop_duplicates("post_id").to_dict("records")
    ]


def _social_data():
    posts = _csv("social_posts.csv")
    labels = _csv("theme_labels.csv")
    labels["confidence"] = pd.to_numeric(labels["confidence"], errors="coerce")
    labels = labels[labels["confidence"] >= MIN_CONFIDENCE]
    taxonomy = _csv("theme_taxonomy.csv")
    taxonomy = taxonomy[taxonomy["active"].str.lower() == "true"]
    taxonomy = pd.concat([
        taxonomy[taxonomy["taxonomy_id"] == "base"],
        taxonomy[taxonomy["taxonomy_id"] == "social_competitive"],
    ]).drop_duplicates("theme_id", keep="last")
    label_map = dict(zip(taxonomy["theme_id"], taxonomy["label"]))
    merged = labels.merge(
        posts[["post_id", "brand", "posted_at"]], on="post_id", how="left"
    )
    return merged, label_map


def _social_signals(store, labels, label_map):
    note = "Facebook only; LinkedIn and Instagram unavailable."
    for theme_id, group in labels.groupby("theme_id"):
        n = len(group)
        candidate = n >= MIN_POSTS
        label = label_map.get(theme_id, theme_id)
        _add(
            store, "social_theme", theme_id,
            f"{label}: {n} Facebook posts", theme_id,
            group["posted_at"].min(), group["posted_at"].max(),
            f"Observed in {n} Facebook posts across {group['brand'].nunique()} brand(s)."
            if candidate else
            f"Insufficient evidence: {n} post(s); not enough to characterize a pattern.",
            "candidate" if candidate else "insufficient",
            round(float(group["confidence"].mean()), 3),
            RULE_SOCIAL, note, _social_evidence(group),
        )


def _current_price_evidence(platform, plan, price, tier, basis):
    tier = int(tier)
    return _ev(
        f"pricing:{platform}:{plan}:{tier}:{basis}",
        "pricing_current",
        f"{platform} {plan}: ${price:g}/month at {tier} {basis}",
    )


def _baseline_price_evidence(platform, plan, price, tier):
    tier = int(tier)
    return _ev(
        f"pricing_baseline:{platform}:{plan}:{tier}",
        "pricing_baseline",
        f"{platform} {plan}: ${price:g}/month at {tier} subscribers",
    )


def _pricing_signals(store, changes):
    rows = changes[
        changes["change_type"].isin(["price_change", "new_plan"])
        | changes["plan_renamed"]
    ]
    for row in rows.to_dict("records"):
        current_tier = int(row["current_tier"])
        tier = f"{current_tier} {row['tier_basis']}"
        baseline_tier = (
            f"{int(row['baseline_tier'])} subscribers"
            if pd.notna(row["baseline_tier"]) else "an unknown baseline tier"
        )
        evidence = [_current_price_evidence(
            row["platform"], row["plan"], row["price"],
            current_tier, row["tier_basis"],
        )]
        if pd.notna(row["baseline_price"]):
            evidence.append(_baseline_price_evidence(
                row["baseline_platform"], row["baseline_plan"],
                row["baseline_price"], row["baseline_tier"],
            ))

        rename = ""
        if row["plan_renamed"]:
            rename = (
                f"Plan renamed from {row['baseline_plan']} to {row['plan']}; "
                f"{row['baseline_plan']} is not a separate current plan."
            )
            evidence.append(_ev(
                f"pricing_rename:{row['platform']}:{row['baseline_plan']}:"
                f"{row['plan']}:{current_tier}:{row['tier_basis']}",
                "pricing_rename",
                rename,
            ))

        if row["change_type"] == "new_plan":
            title = f"{row['platform']} launches {row['plan']} at {tier}"
            summary = (
                f"New plan {row['plan']} at ${row['price']:g}/month for {tier}; "
                "no comparable baseline plan."
            )
        elif row["plan_renamed"] and row["change_type"] == "unchanged":
            title = (
                f"{row['platform']} renames {row['baseline_plan']} "
                f"to {row['plan']} at {tier}"
            )
            summary = (
                f"Plan renamed from {row['baseline_plan']} to {row['plan']}; "
                f"monthly price unchanged at ${row['price']:g} for {tier} "
                f"(baseline {baseline_tier})."
            )
        else:
            title = f"{row['platform']} changes {row['plan']} price at {tier}"
            summary = (
                f"{rename} Monthly price changed from ${row['baseline_price']:g} "
                f"at {baseline_tier} to ${row['price']:g} at {tier} "
                f"({row['price_change_pct']:+.1f}%)."
            ).strip()

        note = (
            f"Monthly USD; baseline Sep 2025; captured {row['captured_at']}; "
            "promotions excluded."
        )
        if row["tier_mismatch"]:
            note += " Tier basis or tier differs from baseline."
        status = "inferential" if row["tier_mismatch"] else "candidate"
        confidence = 0.6 if row["tier_mismatch"] else 1.0
        _add(
            store, "pricing_change",
            f"{row['platform']}:{row['plan']}:{tier}:{row['change_type']}",
            title, row["platform"], "September 2025", row["captured_at"],
            summary, status, confidence, RULE_PRICING, note, evidence,
        )


def _pricing_evidence(brand, baseline, current, changes):
    rows = current[current["platform"] == brand]
    if rows.empty:
        return []
    baseline_platform = rows["baseline_platform"].iloc[0]
    baseline_rows = baseline[
        (baseline["platform"] == baseline_platform)
        & baseline["monthly_price_usd"].notna()
    ]
    current_evidence = [
        _current_price_evidence(
            row["platform"], row["plan"], row["price"],
            row["current_tier"], row["tier_basis"],
        )
        for row in rows.to_dict("records")
    ]
    baseline_evidence = [
        _baseline_price_evidence(
            row["platform"], row["plan"], row["monthly_price_usd"],
            row["subscriber_tier"],
        )
        for row in baseline_rows.to_dict("records")
    ]
    rename_evidence = [
        _ev(
            f"pricing_rename:{brand}:{row['baseline_plan']}:{row['plan']}:"
            f"{int(row['current_tier'])}:{row['tier_basis']}",
            "pricing_rename",
            f"Plan renamed from {row['baseline_plan']} to {row['plan']}; "
            f"{row['baseline_plan']} is not a separate current plan.",
        )
        for row in changes[
            (changes["platform"] == brand) & changes["plan_renamed"]
        ].to_dict("records")
    ]
    return current_evidence + baseline_evidence + rename_evidence


def _cf_signals(store, con):
    mappings = analysis.load_mappings()
    target = pd.read_sql_query("SELECT * FROM klytics_markets", con)
    source = pd.read_sql_query("SELECT * FROM cf_performance", con)
    resolved, issues = analysis.resolve_mappings(
        mappings[mappings["review_status"] == "approved"], target
    )
    if not issues.empty:
        print("Mapping issues:", len(issues))
    metrics = analysis.mapped_metrics(source, resolved, "cf_performance")
    summary = analysis.source_summary(metrics)
    changes = analysis.same_title_change(metrics)
    latest = max(summary["month"])

    primary = summary[
        (summary["relationship"] == "primary") & (summary["month"] == latest)
    ]
    for row in primary.to_dict("records"):
        change = _first(
            changes, source_label=row["source_label"], relationship="primary"
        )
        if change is None:
            continue
        prev, latest_month = change["change_period"].split(" -> ")
        mapping = _first(
            resolved, source_label=row["source_label"],
            relationship="primary", month=latest_month,
        )
        if mapping is None:
            continue

        m = metrics[
            (metrics["source_label"] == row["source_label"])
            & (metrics["relationship"] == "primary")
        ]
        pivot = m.pivot_table(index="asin", columns="month", values="units_per_day")
        cohort = pivot.dropna(subset=[prev, latest_month]).index
        latest_rows = m[
            (m["month"] == latest_month) & (m["asin"].isin(cohort))
        ]

        insufficient = bool(change["insufficient_titles"]) or len(latest_rows) < 5
        if insufficient:
            text = (
                f"Insufficient evidence: {int(change['same_title_n'])} title(s) "
                "for a same-title comparison; not enough to characterize a pattern. "
                f"Mapping confidence {row['confidence']:.2f}."
            )
            status = "insufficient"
        else:
            text = (
                f"Same-title units/day {change['same_title_units_change_pct']:+.1f}% "
                f"vs market growth {row['market_growth_pct']:+.1f}%; "
                f"CF weighted price ${row['weighted_price']:.2f} vs market "
                f"${row['market_avg_price']:.2f} ({row['price_gap_pct']:+.1f}%)."
            )
            status = "candidate"

        note = (
            "Synthetic CF commercial values; K-lytics top-20 market benchmark; "
            f"mapping confidence {row['confidence']:.2f}."
        )
        secondary = resolved[
            (resolved["source_label"] == row["source_label"])
            & (resolved["relationship"] == "secondary")
            & (resolved["month"] == latest_month)
        ]
        if not secondary.empty:
            sec = secondary.iloc[0]
            note += (
                f" Secondary mapping: {sec['target_path']} "
                f"(confidence {sec['confidence']:.2f})."
            )

        evidence = [
            _ev(
                f"klytics:{latest_month}:{mapping['market_id']}",
                "klytics_market",
                f"{mapping['target_path']}: {mapping['avg_sales_per_day_top20']:g} "
                f"sales/day per top-20 title; growth "
                f"{mapping['sales_rank_growth_pct']:g}%; avg price "
                f"${mapping['avg_price']:g}.",
            ),
            _ev(
                f"mapping:{mapping['mapping_id']}",
                "mapping",
                f"{row['source_label']} -> {mapping['target_path']} "
                f"(confidence {row['confidence']:.2f}).",
            ),
        ]
        evidence.extend(
            _ev(
                f"cf:{cf_row['asin']}:{cf_row['month']}",
                "cf_performance",
                f"{cf_row['title']}: {cf_row['units_per_day']:.2f} units/day; "
                f"${cf_row['avg_offer_price']:.2f}; "
                f"{cf_row['net_units_sold']} net units.",
            )
            for cf_row in latest_rows.to_dict("records")
        )
        _add(
            store, "cf_market", row["source_label"],
            f"CF {row['source_label']} vs {row['target_path']}",
            row["source_label"], prev, latest_month,
            text, status, float(row["confidence"]), RULE_CF, note, evidence,
        )


def _cross_source_signals(store, labels, label_map, baseline, current, changes):
    for brand in sorted(labels["brand"].unique()):
        brand_labels = labels[labels["brand"] == brand]
        post_count = brand_labels["post_id"].nunique()
        counts = brand_labels.groupby("theme_id").size().sort_values(ascending=False)
        top = [
            label_map.get(theme_id, theme_id)
            for theme_id in counts[counts >= MIN_POSTS].index[:3]
        ]
        brand_pricing = changes[changes["platform"] == brand]
        if brand_pricing.empty:
            continue
        changed = brand_pricing[
            (brand_pricing["change_type"] != "unchanged")
            | brand_pricing["plan_renamed"]
        ]
        pricing_text = (
            "Pricing unchanged across captured tiers."
            if changed.empty else
            f"Pricing changes observed at {len(changed)} captured price points "
            f"({', '.join(sorted(set(changed['plan'])))})."
        )
        if post_count < MIN_POSTS:
            status, confidence = "insufficient", 0.3
            summary = (
                f"Insufficient social evidence: {post_count} Facebook post(s); "
                f"{pricing_text} No positioning inference."
            )
        else:
            status, confidence = "inferential", 0.7
            themes = (
                f" Recurring Facebook themes: {', '.join(top)}."
                if top else " No recurring theme met the 3-post threshold."
            )
            summary = f"{pricing_text}{themes} Co-occurrence only; no causal link."

        _add(
            store, "cross_source", brand,
            f"{brand}: pricing and Facebook messaging", brand,
            brand_labels["posted_at"].min(),
            max(brand_labels["posted_at"].max(), brand_pricing["captured_at"].max()),
            summary, status, confidence, RULE_CROSS,
            "Cross-source co-occurrence only; no causal link. "
            "Facebook only; LinkedIn and Instagram unavailable.",
            _social_evidence(brand_labels)
            + _pricing_evidence(brand, baseline, current, changes),
        )


def _write(con, store):
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    signals = [
        (
            s["signal_id"], s["signal_type"], s["title"], s["entity"],
            s["period_start"], s["period_end"], s["summary"], s["status"],
            s["confidence"], s["rule_version"], s["coverage_note"], created_at,
        )
        for s in store.values()
    ]
    evidence = [
        (s["signal_id"], e["evidence_id"], e["evidence_type"], e["quote"], e["role"])
        for s in store.values() for e in s["evidence"]
    ]
    con.executemany(
        """
        INSERT OR REPLACE INTO signals (
            signal_id, signal_type, title, entity, period_start, period_end,
            summary, status, confidence, rule_version, coverage_note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        signals,
    )
    con.executemany(
        """
        INSERT OR IGNORE INTO signal_evidence (
            signal_id, evidence_id, evidence_type, quote, role, verified
        ) VALUES (?, ?, ?, ?, ?, 1)
        """,
        evidence,
    )


def generate_signals(db_path=DB):
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM signal_evidence")
    con.execute("DELETE FROM signals")

    labels, label_map = _social_data()
    baseline, current = pricing.load_pricing(con)
    changes = pricing.compare_pricing(baseline, current)
    store = {}
    _social_signals(store, labels, label_map)
    _pricing_signals(store, changes)
    _cf_signals(store, con)
    _cross_source_signals(store, labels, label_map, baseline, current, changes)
    _write(con, store)
    con.commit()

    counts = pd.read_sql_query(
        "SELECT signal_type, status, COUNT(*) AS signals FROM signals "
        "GROUP BY signal_type, status ORDER BY signal_type, status", con
    )
    print(counts.to_string(index=False))
    print("signals:", len(store))
    print("evidence:", con.execute("SELECT COUNT(*) FROM signal_evidence").fetchone()[0])
    con.close()
    return store


if __name__ == "__main__":
    generate_signals()
