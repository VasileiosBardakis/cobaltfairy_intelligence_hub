import sqlite3
import warnings
from datetime import date, datetime
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", message=".*extension is not supported.*")

ROOT = Path(__file__).parent
DATA = ROOT / "cobaltfairy-data"
DB = ROOT / "intel.db"
CURRENT_PRICING = ROOT / "pricing_current.csv"
SOCIAL_POSTS = ROOT / "social_posts.csv"
SOCIAL_COVERAGE = ROOT / "social_coverage.csv"


def num(s):
    return pd.to_numeric(
        s.astype("string").str.replace(r"[$%,]", "", regex=True).str.strip(),
        errors="coerce",
    )


def clean_cols(df):
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    return df


def to_month(v):
    if pd.isna(v):
        return None
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return v.strftime("%Y-%m")
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
        return (pd.Timestamp("1899-12-30") + pd.to_timedelta(float(v), unit="D")).strftime("%Y-%m")
    d = pd.to_datetime(str(v), format="%B %Y", errors="coerce")
    return None if pd.isna(d) else d.strftime("%Y-%m")


def write(df, table, con):
    df.to_sql(table, con, if_exists="replace", index=False)
    print(f"{table}: {len(df)} rows")


K_RENAME = {
    "ID": "market_id",
    "Level": "level",
    "Category Path": "category_path",
    "Category": "category",
    "Sub-category": "subcategory",
    "Sub-subcategory": "subsubcategory",
    "Level 4": "level4",
    "Level 5": "level5",
    "Average Sales Rank of Top 20 Titles": "avg_sales_rank_top20",
    "Average Estimated. Sales per Day per Top 20 Title": "avg_sales_per_day_top20",
    "Average Sales Rank of No. 1 Best-seller": "avg_sales_rank_no1",
    "Est. Sales per Day of No. 1 Bestseller": "sales_per_day_no1",
    "% Rise/ Drop of Top 20 Titles Average Sales Rank": "sales_rank_growth_pct",
    "Average Price of Top 20 Titles": "avg_price",
    "Lowest Price among Top 20 Titles": "lowest_price",
    "Price Change of Top 20 Titles vs. Prior Month": "price_change_pct",
    "Number of Titles": "num_titles",
    "Change of Number of Titles vs. Prior Month": "titles_change_pct",
    "Kindle Unlimited Share": "ku_share_pct",
    "Average Page Length": "avg_page_length",
    "Sales-to-Comp Ratio: Sales Per Day x 1000 divided by No. of Titles": "sales_to_comp",
    "Cluster": "cluster",
    "Amazon Bestseller List Link": "bsl_url",
    "Amazon Category Link (Popularity list)": "cat_url",
    "Browse Tree End Node ID": "browse_node_id",
    "NODE ID": "node_id",
    "Path ID": "path_id",
}
K_NUM = [
    "avg_sales_rank_top20", "avg_sales_per_day_top20", "avg_sales_rank_no1",
    "sales_per_day_no1", "sales_rank_growth_pct", "avg_price", "lowest_price",
    "price_change_pct", "num_titles", "titles_change_pct", "ku_share_pct",
    "avg_page_length", "sales_to_comp",
]
K_COLS = [
    "month", "market_id", "level", "category_path", "category", "subcategory",
    "subsubcategory", "level4", "level5", *K_NUM, "cluster", "bsl_url", "cat_url",
    "browse_node_id", "node_id", "path_id", "source_file", "source_row",
]

frames = []
for path in sorted(DATA.glob("Klytics Report*.csv")):
    month = "2025-05" if "05-2025" in path.name else "2025-04"
    df = clean_cols(pd.read_csv(path, skiprows=5, dtype=str))
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df["source_row"] = df.index + 7
    df["source_file"] = path.name
    df["month"] = month
    df = df[df["ID"].notna()].rename(columns=K_RENAME)
    for c in K_NUM:
        df[c] = num(df[c])
    df["num_titles"] = df["num_titles"].astype("Int64")
    df["avg_page_length"] = df["avg_page_length"].astype("Int64")
    frames.append(df[K_COLS])

klytics = pd.concat(frames, ignore_index=True)
assert len(klytics) == 16244
assert not klytics.duplicated(["month", "market_id"]).any()
assert set(klytics["month"]) == {"2025-04", "2025-05"}

CF_RENAME = {
    "Title": "title", "Author": "author", "ASIN": "asin",
    "Series Name": "series_name", "Series Number": "series_number",
    "Publication Date": "publication_date", "Publisher": "publisher",
    "Genre": "genre", "Subgenre": "subgenre", "Trope": "trope",
    "Amazon URL": "amazon_url", "Reporting Month": "month",
    "Marketplace": "marketplace", "Currency": "currency",
    "Active Days in Period": "active_days", "Units Sold": "units_sold",
    "Units Refunded": "units_refunded", "Net Units Sold": "net_units_sold",
    "Royalty Type": "royalty_type", "Transaction Type": "transaction_type",
    "Avg. List Price without tax": "avg_list_price",
    "Avg. Offer Price without tax": "avg_offer_price",
    "Avg. File Size (MB)": "avg_file_size_mb",
    "Avg. Delivery Cost": "avg_delivery_cost", "Royalty": "royalty",
}
CF_NUM = [
    "series_number", "active_days", "units_sold", "units_refunded",
    "net_units_sold", "avg_list_price", "avg_offer_price", "avg_file_size_mb",
    "avg_delivery_cost", "royalty",
]
CF_INT = ["series_number", "active_days", "units_sold", "units_refunded", "net_units_sold"]
CF_COLS = [
    "title", "author", "asin", "series_name", "series_number", "publication_date",
    "publisher", "genre", "subgenre", "trope", "amazon_url", "month",
    "marketplace", "currency", "active_days", "units_sold", "units_refunded",
    "net_units_sold", "royalty_type", "transaction_type", "avg_list_price",
    "avg_offer_price", "avg_file_size_mb", "avg_delivery_cost", "royalty",
    "source_file", "source_row",
]

cf = pd.read_excel(DATA / "CF_Catalogue_Performance.xlsx", sheet_name="CF Performance")
cf = cf.rename(columns=CF_RENAME)
cf["source_row"] = cf.index + 2
cf["source_file"] = "CF_Catalogue_Performance.xlsx"
pub = cf["publication_date"]
cf["publication_date"] = (
    (pd.Timestamp("1899-12-30") + pd.to_timedelta(pub, unit="D")).dt.date
    if pd.api.types.is_numeric_dtype(pub)
    else pd.to_datetime(pub, errors="coerce").dt.date
)
cf["month"] = cf["month"].map(to_month)
for c in CF_NUM:
    cf[c] = num(cf[c])
for c in CF_INT:
    cf[c] = cf[c].astype("Int64")
cf = cf[CF_COLS]

assert len(cf) == 70
assert cf["asin"].nunique() == 47
assert not cf.duplicated(["asin", "month"]).any()
assert set(cf["month"]) == {"2025-04", "2025-05"}
assert (cf["net_units_sold"] == cf["units_sold"] - cf["units_refunded"]).all()

P_RENAME = {
    "Platform": "platform", "Subscriber Reference": "subscriber_tier",
    "Plan": "plan", "Monthly Price (USD)": "monthly_price_usd",
    "Pricing Type": "pricing_type", "Baseline Period": "baseline_period",
    "Notes": "notes",
}
pricing = pd.read_excel(
    DATA / "FairyMail_Competitor_Pricing_Sep2025.xlsx",
    sheet_name="Normalized Price Points",
).rename(columns=P_RENAME)
pricing["source_row"] = pricing.index + 2
pricing["source_file"] = "FairyMail_Competitor_Pricing_Sep2025.xlsx"
pricing["subscriber_tier"] = num(pricing["subscriber_tier"]).astype("Int64")
pricing["monthly_price_usd"] = num(pricing["monthly_price_usd"])
pricing = pricing[
    ["platform", "subscriber_tier", "plan", "monthly_price_usd", "pricing_type",
     "baseline_period", "notes", "source_file", "source_row"]
]

assert len(pricing) == 48
assert pricing["platform"].nunique() == 8
assert not pricing.duplicated(["platform", "subscriber_tier", "plan"]).any()

M_RENAME = {
    "Platform": "platform", "Free Plan / Trial Details": "free_plan_details",
    "Annual Subscription / Discount": "annual_discount",
    "Total Number of Tiers": "total_tiers", "Custom Plan": "custom_plan",
    "Baseline Period": "baseline_period", "Original Currency": "original_currency",
    "Notes": "notes",
}
meta = pd.read_excel(
    DATA / "FairyMail_Competitor_Pricing_Sep2025.xlsx",
    sheet_name="Pricing Baseline",
).rename(columns=M_RENAME)
meta["source_row"] = meta.index + 2
meta["source_file"] = "FairyMail_Competitor_Pricing_Sep2025.xlsx"
meta["total_tiers"] = meta["total_tiers"].astype("string")
meta = meta[
    ["platform", "free_plan_details", "annual_discount", "total_tiers",
     "custom_plan", "baseline_period", "original_currency", "notes",
     "source_file", "source_row"]
]

assert len(meta) == 8

current = pd.DataFrame()
if CURRENT_PRICING.exists():
    current = pd.read_csv(CURRENT_PRICING, dtype=str, keep_default_na=False)
    current["source_row"] = current.index + 2
    current["source_file"] = CURRENT_PRICING.name
    current["price"] = num(current["price"])
    current["baseline_tier"] = num(current["baseline_tier"]).astype("Int64")
    current["current_tier"] = num(current["current_tier"]).astype("Int64")
    current["captured_at"] = pd.to_datetime(current["captured_at"], errors="coerce").dt.date

social = pd.DataFrame()
if SOCIAL_POSTS.exists():
    social = pd.read_csv(SOCIAL_POSTS, dtype=str, keep_default_na=False)
    social["source_row"] = social.index + 2
    social["source_file"] = SOCIAL_POSTS.name
    social["posted_at"] = pd.to_datetime(social["posted_at"], errors="coerce").dt.date
    social["captured_at"] = pd.to_datetime(social["captured_at"], errors="coerce").dt.date
    assert not social["post_id"].duplicated().any()
    assert social["posted_at"].notna().all()

coverage = pd.DataFrame()
if SOCIAL_COVERAGE.exists():
    coverage = pd.read_csv(SOCIAL_COVERAGE, dtype=str, keep_default_na=False)
    coverage["source_row"] = coverage.index + 2
    coverage["source_file"] = SOCIAL_COVERAGE.name
    coverage["posts_captured"] = num(coverage["posts_captured"]).astype("Int64")
    coverage["window_start"] = pd.to_datetime(coverage["window_start"], errors="coerce").dt.date
    coverage["window_end"] = pd.to_datetime(coverage["window_end"], errors="coerce").dt.date
    coverage["captured_at"] = pd.to_datetime(coverage["captured_at"], errors="coerce").dt.date

with sqlite3.connect(DB) as con:
    write(klytics, "klytics_markets", con)
    write(cf, "cf_performance", con)
    write(pricing, "pricing_baseline", con)
    write(meta, "pricing_meta", con)
    if current.empty:
        con.execute("DROP TABLE IF EXISTS pricing_current")
    else:
        write(current, "pricing_current", con)
    if social.empty:
        con.execute("DROP TABLE IF EXISTS social_posts")
    else:
        write(social, "social_posts", con)
    if coverage.empty:
        con.execute("DROP TABLE IF EXISTS social_coverage")
    else:
        write(coverage, "social_coverage", con)

    assert con.execute(
        "select net_units_sold, round(royalty, 2) from cf_performance "
        "where asin='B0F3DMLVQY' and month='2025-05'"
    ).fetchone() == (374, 994.84)
    assert con.execute(
        "select monthly_price_usd from pricing_baseline "
        "where platform='Mailchimp' and subscriber_tier=500 and plan='Essentials'"
    ).fetchone() == (13.0,)

print("months:", klytics.groupby("month").size().to_dict())
print("done")
