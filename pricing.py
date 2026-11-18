import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DB = ROOT / "intel.db"


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
