import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DB = ROOT / "data" / "intel.db"


def load_pricing(con):
    baseline = pd.read_sql_query("SELECT * FROM pricing_baseline", con)
    current = pd.read_sql_query("SELECT * FROM pricing_current", con)
    return baseline, current


def compare_pricing(baseline, current):
    baseline = baseline.rename(columns={
        "platform": "baseline_platform_name",
        "plan": "baseline_plan_name",
        "subscriber_tier": "baseline_tier_value",
        "monthly_price_usd": "baseline_price",
        "notes": "baseline_notes",
    })[[
        "baseline_platform_name", "baseline_plan_name", "baseline_tier_value",
        "baseline_price", "pricing_type", "baseline_period", "baseline_notes",
    ]]

    merged = current.merge(
        baseline,
        left_on=["baseline_platform", "baseline_plan", "baseline_tier"],
        right_on=["baseline_platform_name", "baseline_plan_name", "baseline_tier_value"],
        how="left",
    )
    merged["price_change"] = merged["price"] - merged["baseline_price"]
    merged["price_change_pct"] = (
        merged["price_change"] / merged["baseline_price"] * 100
    )
    merged["plan_renamed"] = (
        merged["baseline_plan"].ne("") & merged["plan"].ne(merged["baseline_plan"])
    )
    merged["tier_mismatch"] = (
        merged["tier_basis"].ne("subscribers")
        | merged["current_tier"].ne(merged["baseline_tier"])
    )
    merged["change_type"] = merged.apply(_change_type, axis=1)

    columns = [
        "platform", "baseline_platform", "plan", "baseline_plan",
        "baseline_tier", "current_tier", "tier_basis", "baseline_price",
        "price", "price_change", "price_change_pct", "change_type",
        "plan_renamed", "tier_mismatch", "pricing_type", "source_url",
        "captured_at", "notes", "baseline_notes",
    ]
    return merged[columns].sort_values(
        ["platform", "baseline_tier", "plan"], na_position="last"
    ).reset_index(drop=True)


def _change_type(row):
    if pd.isna(row["baseline_price"]):
        return "new_plan" if not row["baseline_plan"] else "baseline_unavailable"
    if abs(row["price_change"]) < 0.005:
        return "unchanged"
    return "price_change"


def coverage_summary(baseline, current, changes):
    if baseline.empty or current.empty or changes.empty:
        return pd.DataFrame()

    baseline = baseline.copy()
    baseline["monthly_price_usd"] = pd.to_numeric(
        baseline["monthly_price_usd"], errors="coerce"
    )
    mapping = changes[["baseline_platform", "platform"]].drop_duplicates()
    platform_map = dict(zip(mapping["baseline_platform"], mapping["platform"]))
    baseline["provider"] = baseline["platform"].map(platform_map).fillna(
        baseline["platform"]
    )
    priced = baseline[baseline["monthly_price_usd"].notna()]
    baseline_counts = priced.groupby("provider").size()
    current_counts = current.groupby("platform").size()

    matched = changes[changes["baseline_price"].notna()].copy()
    matched["provider"] = matched["baseline_platform"].map(platform_map).fillna(
        matched["baseline_platform"]
    )
    matched = matched.drop_duplicates(
        ["provider", "baseline_plan", "baseline_tier"]
    )
    matched_counts = matched.groupby("provider").size()
    mismatch_counts = changes[changes["tier_mismatch"]].groupby("platform").size()

    def caveat(provider):
        rows = current[current["platform"] == provider]
        notes = sorted({
            str(note).strip()
            for note in rows["notes"]
            if pd.notna(note) and str(note).strip()
        })
        if notes:
            return "; ".join(notes)
        if mismatch_counts.get(provider, 0):
            return "Tier basis or tier differs from baseline."
        return ""

    providers = sorted(set(baseline_counts.index) | set(current_counts.index))
    rows = []
    for provider in providers:
        baseline_points = int(baseline_counts.get(provider, 0))
        captured_points = int(current_counts.get(provider, 0))
        matched_points = int(matched_counts.get(provider, 0))
        rows.append({
            "Provider": provider,
            "Baseline priced points": baseline_points,
            "Captured points": captured_points,
            "Matched baseline points": matched_points,
            "Unmatched baseline points": max(baseline_points - matched_points, 0),
            "Tier mismatches": int(mismatch_counts.get(provider, 0)),
            "Caveat": caveat(provider),
        })
    return pd.DataFrame(rows)


def main():
    with sqlite3.connect(DB) as con:
        baseline, current = load_pricing(con)

    changes = compare_pricing(baseline, current)
    print(f"current pricing rows: {len(current)}")
    print("change types:", changes["change_type"].value_counts().to_dict())
    print(changes[[
        "platform", "plan", "baseline_plan", "baseline_tier", "baseline_price",
        "price", "price_change_pct", "change_type", "plan_renamed",
        "tier_mismatch",
    ]].to_string(index=False))

    assert not current.empty
    assert changes["price"].notna().all()
    assert not changes.duplicated(
        ["platform", "plan", "current_tier", "tier_basis"]
    ).any()
    print("done")


if __name__ == "__main__":
    main()
