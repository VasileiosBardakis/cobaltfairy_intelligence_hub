import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DB = ROOT / "data" / "intel.db"
MAPPINGS = ROOT / "data" / "mappings.csv"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_mappings(path=MAPPINGS):
    mappings = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {
        "source_table", "source_field", "source_label", "target_table",
        "target_level", "target_path", "relationship", "confidence",
        "method", "rationale", "review_status",
    }
    missing = required - set(mappings.columns)
    if missing:
        raise ValueError(f"Missing mapping columns: {sorted(missing)}")

    mappings["confidence"] = pd.to_numeric(mappings["confidence"], errors="coerce")
    mappings["mapping_id"] = mappings[
        ["source_table", "source_field", "source_label", "target_path"]
    ].agg("|".join, axis=1)
    return mappings


def resolve_mappings(mappings, target, months=None):
    target = target.copy()
    if months is not None:
        target = target[target["month"].isin(months)]

    rows, issues = [], []
    for mapping in mappings.itertuples(index=False):
        matches = target[
            (target["level"] == mapping.target_level)
            & (target["category_path"] == mapping.target_path)
        ]
        if matches.empty:
            issues.append({"mapping_id": mapping.mapping_id, "month": None,
                           "issue": "no target row"})
            continue

        for month, group in matches.groupby("month", dropna=False):
            if len(group) != 1:
                issues.append({"mapping_id": mapping.mapping_id, "month": month,
                               "issue": f"{len(group)} target rows"})
                continue
            row = mapping._asdict()
            row.update(group.iloc[0].to_dict())
            rows.append(row)

    resolved = pd.DataFrame(rows)
    if not resolved.empty:
        resolved = resolved.rename(columns={
            "source_file": "target_source_file",
            "source_row": "target_source_row",
        })
    return resolved, pd.DataFrame(issues)


def unmapped_labels(source, source_table, source_field, mappings):
    if source_field not in source.columns:
        raise KeyError(f"Missing source field: {source_field}")
    labels = set(source[source_field].dropna().astype(str))
    approved = mappings[
        (mappings["source_table"] == source_table)
        & (mappings["source_field"] == source_field)
        & (mappings["review_status"] == "approved")
    ]
    return sorted(labels - set(approved["source_label"]))


def _similarity(label, path):
    label, path = label.lower(), path.lower()
    sequence = SequenceMatcher(None, label, path).ratio()
    label_tokens = set(re.findall(r"[a-z0-9]+", label))
    path_tokens = set(re.findall(r"[a-z0-9]+", path))
    overlap = len(label_tokens & path_tokens) / max(1, len(label_tokens))
    return round(0.5 * sequence + 0.5 * overlap, 3)


def suggest_mappings(label, target, target_level, top_n=3):
    paths = target.loc[target["level"] == target_level, "category_path"].dropna().unique()
    ranked = sorted(((_similarity(label, path), path) for path in paths), reverse=True)[:top_n]
    return pd.DataFrame(ranked, columns=["score", "target_path"]).assign(target_level=target_level)


def mapped_metrics(source, resolved, source_table):
    resolved = resolved[resolved["source_table"] == source_table]
    parts = []
    for (source_field, source_label), mappings in resolved.groupby(["source_field", "source_label"]):
        if source_field not in source.columns:
            raise KeyError(f"Missing source field: {source_field}")
        rows = source[source[source_field].astype(str) == source_label]
        parts.append(rows.merge(mappings, on="month", how="inner"))

    if not parts:
        return pd.DataFrame()

    metrics = pd.concat(parts, ignore_index=True)
    metrics["units_per_day"] = metrics["net_units_sold"] / metrics["active_days"]
    metrics["royalty_per_day"] = metrics["royalty"] / metrics["active_days"]
    metrics["price_gap_pct"] = (
        (metrics["avg_offer_price"] - metrics["avg_price"]) / metrics["avg_price"] * 100
    )

    identity = metrics["asin"].astype(str) if "asin" in metrics else metrics["source_label"]
    metrics["source_evidence"] = (
        metrics["source_table"] + ":" + identity + ":" + metrics["month"]
    )
    metrics["target_evidence"] = (
        metrics["target_table"] + ":" + metrics["target_path"] + ":" + metrics["month"]
    )
    return metrics


def source_summary(metrics, id_col="asin", min_titles=5):
    if metrics.empty:
        return metrics

    metrics = metrics.copy()
    metrics["price_x_units"] = metrics["avg_offer_price"] * metrics["net_units_sold"]
    keys = [
        "source_table", "source_field", "source_label", "relationship",
        "target_level", "target_path", "month",
    ]
    summary = metrics.groupby(keys, dropna=False).agg(
        titles=(id_col, "nunique"),
        net_units=("net_units_sold", "sum"),
        royalty=("royalty", "sum"),
        units_per_day=("units_per_day", "mean"),
        royalty_per_day=("royalty_per_day", "mean"),
        price_x_units=("price_x_units", "sum"),
        market_sales_per_day=("avg_sales_per_day_top20", "first"),
        market_growth_pct=("sales_rank_growth_pct", "first"),
        market_avg_price=("avg_price", "first"),
        market_sales_to_comp=("sales_to_comp", "first"),
        market_num_titles=("num_titles", "first"),
        confidence=("confidence", "first"),
        review_status=("review_status", "first"),
    ).reset_index()
    summary["weighted_price"] = summary["price_x_units"] / summary["net_units"]
    summary["price_gap_pct"] = (
        (summary["weighted_price"] - summary["market_avg_price"])
        / summary["market_avg_price"] * 100
    )
    summary["insufficient_titles"] = summary["titles"] < min_titles
    return summary.drop(columns="price_x_units")


def same_title_change(metrics, id_col="asin", min_titles=5):
    months = sorted(metrics["month"].dropna().unique())
    if len(months) < 2:
        return pd.DataFrame()

    previous, latest = months[-2], months[-1]
    keys = [
        "source_table", "source_field", "source_label", "relationship",
        "target_level", "target_path",
    ]
    wide = metrics.pivot_table(
        index=keys + [id_col], columns="month",
        values=["units_per_day", "royalty_per_day"], aggfunc="first",
    )
    wide.columns = [f"{value}_{month}" for value, month in wide.columns]

    required = [
        f"units_per_day_{previous}", f"units_per_day_{latest}",
        f"royalty_per_day_{previous}", f"royalty_per_day_{latest}",
    ]
    if not set(required).issubset(wide.columns):
        return pd.DataFrame()

    wide = wide.dropna(subset=[f"units_per_day_{previous}", f"units_per_day_{latest}"]).copy()
    wide["units_change_pct"] = (
        wide[f"units_per_day_{latest}"] / wide[f"units_per_day_{previous}"] - 1
    ) * 100
    wide["royalty_change_pct"] = (
        wide[f"royalty_per_day_{latest}"] / wide[f"royalty_per_day_{previous}"] - 1
    ) * 100

    changes = wide.reset_index().groupby(keys, dropna=False).agg(
        same_title_n=(id_col, "nunique"),
        same_title_units_change_pct=("units_change_pct", "median"),
        same_title_royalty_change_pct=("royalty_change_pct", "median"),
    ).reset_index()
    changes["change_period"] = f"{previous} -> {latest}"
    changes["insufficient_titles"] = changes["same_title_n"] < min_titles
    return changes


def market_view(con, table, level, month=None, search=None,
                min_sales=None, min_growth=None, limit=200):
    if not IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    if month is None:
        month = con.execute(f'SELECT MAX(month) FROM "{table}"').fetchone()[0]

    query = f'SELECT * FROM "{table}" WHERE level = ? AND month = ?'
    params = [level, month]
    if search:
        query += " AND category_path LIKE ?"
        params.append(f"%{search}%")
    if min_sales is not None:
        query += " AND avg_sales_per_day_top20 >= ?"
        params.append(min_sales)
    if min_growth is not None:
        query += " AND sales_rank_growth_pct >= ?"
        params.append(min_growth)
    query += " ORDER BY avg_sales_per_day_top20 DESC LIMIT ?"
    params.append(limit)
    return pd.read_sql_query(query, con, params=params)


def main():
    mappings = load_mappings()
    approved = mappings[mappings["review_status"] == "approved"]

    with sqlite3.connect(DB) as con:
        source = pd.read_sql_query("SELECT * FROM cf_performance", con)
        target = pd.read_sql_query("SELECT * FROM klytics_markets", con)

        print(f"mappings: {len(mappings)} ({len(approved)} approved)")
        missing = unmapped_labels(source, "cf_performance", "subgenre", approved)
        print("unmapped labels:", missing or "none")

        resolved, issues = resolve_mappings(approved, target)
        print(f"resolved mapping rows: {len(resolved)}")
        if not issues.empty:
            print(issues.to_string(index=False))

        metrics = mapped_metrics(source, resolved, "cf_performance")
        summary = source_summary(metrics)
        changes = same_title_change(metrics)

        print(f"title-month-mapping rows: {len(metrics)}")
        print(f"summary rows: {len(summary)}")
        print(summary[[
            "source_label", "month", "relationship", "titles",
            "net_units", "market_sales_per_day", "market_growth_pct",
            "price_gap_pct",
        ]].to_string(index=False))
        print("same-title change:")
        print(changes[[
            "source_label", "relationship", "same_title_n",
            "same_title_units_change_pct", "insufficient_titles",
        ]].to_string(index=False))

        assert issues.empty
        assert not metrics.empty
        assert not summary.empty
        assert not changes.empty

    print("done")


if __name__ == "__main__":
    main()
