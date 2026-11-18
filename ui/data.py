import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st

import analysis
import pricing
try:
    import synthetic_demo
except ImportError:
    synthetic_demo = None

from .theme import LOW_CONFIDENCE, STATUS_RANK, _confidence_label, _evidence_label

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "intel.db"
BRIEF_COLUMNS = [
    "brief_id", "signal_id", "model", "prompt_version", "input_hash",
    "positioning", "checker_status", "checker_note", "created_at",
]
CLAIM_COLUMNS = [
    "claim_id", "brief_id", "signal_id", "claim_text", "evidence_ids",
    "quote", "verification_status", "checker_note", "created_at",
]


def _query(con, sql, columns=None):
    try:
        return pd.read_sql_query(sql, con)
    except Exception:
        return pd.DataFrame(columns=columns or [])


@st.cache_data(show_spinner=False)
def load_data(mode):
    if not DB.exists():
        return {"error": f"Database not found at {DB}."}
    if mode == "synthetic" and synthetic_demo is None:
        return {"error": "Synthetic demo files are not available."}

    with closing(sqlite3.connect(DB)) as con:
        try:
            real_signals = pd.read_sql_query(
                "SELECT * FROM signals ORDER BY signal_type, status, title", con
            )
            real_evidence = pd.read_sql_query(
                "SELECT * FROM signal_evidence ORDER BY signal_id, evidence_type, evidence_id",
                con,
            )
        except sqlite3.OperationalError as exc:
            return {"error": f"Database is not initialized: {exc}"}
        real_briefs = _query(
            con, "SELECT * FROM briefs ORDER BY created_at, brief_id",
            BRIEF_COLUMNS,
        )
        real_claims = _query(
            con, "SELECT * FROM claims ORDER BY created_at, claim_id",
            CLAIM_COLUMNS,
        )
        try:
            real_coverage = pd.read_sql_query(
                "SELECT * FROM social_coverage ORDER BY brand, platform", con
            )
            real_social = pd.read_sql_query("SELECT * FROM social_posts", con)
            baseline, current = pricing.load_pricing(con)
            cf = pd.read_sql_query("SELECT * FROM cf_performance", con)
            markets = pd.read_sql_query("SELECT * FROM klytics_markets", con)
        except sqlite3.OperationalError as exc:
            return {"error": f"Database is not initialized: {exc}"}

    theme_path = DATA / "theme_labels.csv"
    real_theme_labels = (
        pd.read_csv(theme_path, dtype=str, keep_default_na=False)
        if theme_path.exists()
        else pd.DataFrame(columns=["post_id", "theme_id", "confidence"])
    )
    mappings = analysis.load_mappings()
    approved = mappings[mappings["review_status"] == "approved"]
    resolved, issues = analysis.resolve_mappings(approved, markets)
    metrics = analysis.mapped_metrics(cf, resolved, "cf_performance")
    summary = analysis.source_summary(metrics)
    same_title = analysis.same_title_change(metrics)

    if mode == "synthetic":
        demo = synthetic_demo.build_demo()
        keep_types = {"pricing_change", "cf_market"}
        keep_ids = set(
            real_signals.loc[
                real_signals["signal_type"].isin(keep_types), "signal_id"
            ]
        )
        signals = pd.concat(
            [
                real_signals[real_signals["signal_id"].isin(keep_ids)],
                demo["signals"],
            ],
            ignore_index=True,
        )
        evidence = pd.concat(
            [
                real_evidence[real_evidence["signal_id"].isin(keep_ids)],
                demo["evidence"],
            ],
            ignore_index=True,
        )
        briefs = pd.concat(
            [
                real_briefs[real_briefs["signal_id"].isin(keep_ids)],
                demo["briefs"],
            ],
            ignore_index=True,
        )
        claims = pd.concat(
            [
                real_claims[real_claims["signal_id"].isin(keep_ids)],
                demo["claims"],
            ],
            ignore_index=True,
        )
        coverage = demo["coverage"]
        social = demo["social"]
        theme_labels = demo["theme_labels"]
    else:
        signals = real_signals
        evidence = real_evidence
        briefs = real_briefs
        claims = real_claims
        coverage = real_coverage
        social = real_social
        theme_labels = real_theme_labels

    return {
        "signals": signals,
        "evidence": evidence,
        "briefs": briefs,
        "claims": claims,
        "coverage": coverage,
        "social": social,
        "cf": cf,
        "baseline": baseline,
        "current": current,
        "mappings": mappings,
        "issues": issues,
        "summary": summary,
        "same_title": same_title,
        "theme_labels": theme_labels,
        "pricing_changes": pricing.compare_pricing(baseline, current),
        "mode": mode,
    }


def _month_range(values):
    months = sorted(str(value) for value in pd.Series(values).dropna().unique())
    if not months:
        return "n/a"
    return months[0] if len(months) == 1 else f"{months[0]} to {months[-1]}"


def _date_range(values):
    dates = pd.to_datetime(pd.Series(values), errors="coerce").dropna()
    if dates.empty:
        return "n/a"
    low, high = dates.min(), dates.max()
    return f"{low:%Y-%m-%d}" if low == high else f"{low:%Y-%m-%d} to {high:%Y-%m-%d}"


def _span(start, end):
    starts = pd.to_datetime(pd.Series(start), errors="coerce").dropna()
    ends = pd.to_datetime(pd.Series(end), errors="coerce").dropna()
    if starts.empty or ends.empty:
        return "n/a"
    return f"{starts.min():%Y-%m-%d} to {ends.max():%Y-%m-%d}"


def _period(start, end):
    start, end = str(start), str(end)
    return start if start == end else f"{start} to {end}"


def _period_rows(data):
    baseline = ", ".join(sorted({
        str(value).strip()
        for value in data["baseline"]["baseline_period"].dropna()
        if str(value).strip()
    }))
    return [
        ("CF & K-lytics", _month_range(data["cf"]["month"])),
        ("Pricing baseline", baseline or "n/a"),
        ("Pricing captured", _date_range(data["current"]["captured_at"])),
        ("Social posts", _date_range(data["social"]["posted_at"])),
        ("Coverage window", _span(
            data["coverage"]["window_start"], data["coverage"]["window_end"]
        )),
    ]


def _theme_label_map():
    path = DATA / "theme_taxonomy.csv"
    if not path.exists():
        return {}
    taxonomy = pd.read_csv(path, dtype=str, keep_default_na=False)
    active = taxonomy[taxonomy["active"].str.lower() == "true"]
    base = active[active["taxonomy_id"] == "base"]
    social = active[active["taxonomy_id"] == "social_competitive"]
    effective = pd.concat([base, social]).drop_duplicates(
        "theme_id", keep="last"
    )
    return dict(zip(effective["theme_id"], effective["label"]))


def _pricing_view(changes):
    view = changes.copy()
    for column in ["baseline_price", "price", "price_change_pct"]:
        view[column] = pd.to_numeric(view[column], errors="coerce")

    def change_text(row):
        if row["change_type"] == "new_plan":
            return "New plan"
        if row["change_type"] == "unchanged":
            return "No change"
        if pd.isna(row["price_change_pct"]):
            return "n/a"
        return f"{row['price_change_pct']:+.1f}%"

    def tier_text(row):
        if pd.isna(row["current_tier"]):
            return "n/a"
        return f"{int(row['current_tier']):,} {row['tier_basis']}"

    def note_text(row):
        note = str(row["notes"]).strip()
        if note:
            return note
        if row["tier_mismatch"]:
            return "Tier basis differs from baseline."
        return ""

    return pd.DataFrame({
        "Provider": view["platform"],
        "Plan": view["plan"],
        "Previous plan": view["baseline_plan"].replace("", "?"),
        "Tier": view.apply(tier_text, axis=1),
        "Baseline": view["baseline_price"],
        "Now": view["price"],
        "Change": view.apply(change_text, axis=1),
        "Caveat": view.apply(note_text, axis=1),
        "Captured": view["captured_at"],
        "Source": view["source_url"],
    })


def _evidence_count(evidence_ids):
    try:
        values = json.loads(evidence_ids)
    except (TypeError, ValueError):
        return 0
    return len(values) if isinstance(values, list) else 0


def _evidence_view(rows):
    view = pd.DataFrame({
        "Source": rows["evidence_type"].map(_evidence_label),
        "Evidence": rows["quote"],
    })
    return view.drop_duplicates()


def _prioritized(signals):
    view = signals.copy()
    view["_confidence"] = pd.to_numeric(view["confidence"], errors="coerce")
    view["_rank"] = view["status"].map(STATUS_RANK).fillna(len(STATUS_RANK))
    return view.sort_values(["_rank", "_confidence"], ascending=[True, False])


def _top_per_type(signals, per_type=1):
    return _prioritized(signals).groupby("signal_type", group_keys=False).head(per_type)


def _uncertain(signals):
    confidence = pd.to_numeric(signals["confidence"], errors="coerce")
    return signals[(signals["status"] == "insufficient") | (confidence < LOW_CONFIDENCE)]


def _quadrant(row):
    cf_value = row["same_title_units_change_pct"]
    market_value = row["market_growth_pct"]
    if pd.isna(cf_value) or pd.isna(market_value):
        return "not comparable"
    if cf_value >= 0 and market_value < 0:
        return "CF up, market down"
    if cf_value < 0 and market_value >= 0:
        return "CF down, market up"
    if cf_value >= 0:
        return "CF up, market up"
    return "CF down, market down"


def _cf_findings(summary, same_title):
    if summary.empty or same_title.empty:
        return pd.DataFrame()

    latest = sorted(summary["month"].dropna().unique())[-1]
    rows = summary[summary["month"] == latest].copy()
    changes = same_title.drop(columns=["insufficient_titles"], errors="ignore")
    keys = ["source_label", "relationship", "target_level", "target_path"]
    rows = rows.merge(
        changes[keys + [
            "change_period", "same_title_n", "same_title_units_change_pct",
            "same_title_royalty_change_pct",
        ]],
        on=keys,
        how="left",
    )
    rows["relative_units_gap"] = (
        rows["same_title_units_change_pct"] - rows["market_growth_pct"]
    )
    rows["quadrant"] = rows.apply(_quadrant, axis=1)
    return rows


def _finding_sentence(row):
    return (
        f"{row['source_label']} ({row['relationship']}): same-title units/day "
        f"{row['same_title_units_change_pct']:+.1f}% vs market "
        f"{row['market_growth_pct']:+.1f}% (gap "
        f"{row['relative_units_gap']:+.1f} pp); price gap "
        f"{row['price_gap_pct']:+.1f}%; "
        f"{_confidence_label(row['confidence']).lower()} mapping confidence."
    )
