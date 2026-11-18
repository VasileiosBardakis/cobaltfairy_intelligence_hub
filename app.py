import html
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import analysis
import pricing
import synthetic_demo

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "intel.db"
LOW_CONFIDENCE = 0.7
STATUS_RANK = {"candidate": 0, "inferential": 1, "insufficient": 2}
STATUS_TONES = {
    "candidate": "cobalt",
    "inferential": "violet",
    "insufficient": "amber",
}
CLAIM_TONES = {
    "verified": "green",
    "inferential": "amber",
    "unsupported": "red",
}
CF_COLORS = {
    "CF up, market down": "#2E9B7A",
    "CF down, market up": "#D64A5A",
    "CF up, market up": "#2F63F7",
    "CF down, market down": "#F0A05A",
    "not comparable": "#9AA1B2",
}
PLATFORM_COLORS = [
    "#2F63F7", "#7C5CBF", "#F0A05A", "#2E9B7A", "#D64A5A", "#6B7280",
]

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Merriweather:wght@400;700;900&display=swap');
:root {
  --ink: #252525;
  --muted: #6B7280;
  --cobalt: #2F63F7;
  --cobalt-deep: #1F4FD8;
  --blue-soft: #EEF3FF;
  --blue-line: #DCE7FF;
  --lavender: #7C5CBF;
  --lavender-soft: #F2EDFB;
  --mint: #2E9B7A;
  --mint-soft: #E8F6F1;
  --peach: #F0A05A;
  --peach-soft: #FDF2E9;
  --danger: #D64A5A;
  --canvas: #FFFFFF;
  --soft: #F7F8FC;
  --line: #E6E9F2;
  --font-display: 'Merriweather', Georgia, 'Times New Roman', serif;
  --font-body: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
html, body, [class*="css"] { font-family: var(--font-body); }
.stApp {
  background:
    radial-gradient(circle at 92% 3%, rgba(47, 99, 247, 0.08), transparent 28%),
    radial-gradient(circle at 4% 94%, rgba(240, 160, 90, 0.09), transparent 24%),
    var(--canvas);
  color: var(--ink);
}
[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1480px; }
h1, h2, h3 { font-family: var(--font-display); }
[data-testid="stHeading"] h3,
[data-testid="stMarkdownContainer"] h3 {
  color: var(--ink);
  font-weight: 900;
  letter-spacing: -0.02em;
  margin-top: 1.4rem;
}
p, li, [data-testid="stMarkdownContainer"] p { line-height: 1.65; }
[data-testid="stCaptionContainer"] p { color: var(--muted); }
section[data-testid="stSidebar"] {
  background: var(--soft);
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] > div { background: transparent; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: var(--ink); }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--muted); }
.brand {
  display: flex; align-items: center; gap: 12px; padding: 6px 2px 20px;
  border-bottom: 1px solid var(--line); margin-bottom: 22px;
}
.brand-mark {
  position: relative; width: 50px; height: 50px; border-radius: 50%;
  background: var(--blue-soft); border: 1px solid var(--blue-line);
}
.brand-mark .wing {
  position: absolute; top: 11px; width: 18px; height: 28px;
  background: var(--cobalt);
  border-radius: 60% 60% 45% 45% / 55% 55% 45% 45%;
}
.brand-mark .wing-left { left: 6px; transform: rotate(-28deg); }
.brand-mark .wing-right { right: 6px; transform: rotate(28deg); }
.brand-eyebrow {
  color: var(--cobalt); font-size: 10px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
}
.brand-title {
  color: var(--ink); font-family: var(--font-display);
  font-size: 1.28rem; font-weight: 900; line-height: 1.15;
}
.side-section { margin-bottom: 24px; }
.side-label {
  color: var(--cobalt); font-size: 10px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 10px;
}
.side-period {
  background: #FFFFFF; border: 1px solid var(--line);
  border-radius: 14px; padding: 10px 12px; margin-bottom: 8px;
  box-shadow: 0 4px 14px rgba(47, 99, 247, 0.04);
}
.side-period-label {
  color: var(--muted); font-size: 10px; letter-spacing: 0.08em;
  text-transform: uppercase;
}
.side-period-value { color: var(--ink); font-size: 13px; font-weight: 600; margin-top: 3px; }
.side-note {
  color: var(--muted); font-size: 11px; line-height: 1.6;
  border-top: 1px solid var(--line);
  padding-top: 16px; margin-top: 6px;
}
.side-pill {
  display: inline-block; border-radius: 999px; padding: 4px 9px;
  margin: 0 5px 6px 0; font-size: 10px; font-weight: 700;
  letter-spacing: 0.02em;
}
.side-pill-cobalt { background: var(--cobalt); color: #FFFFFF; }
.side-pill-violet { background: var(--lavender-soft); color: #6841B4; }
.side-pill-amber { background: var(--peach-soft); color: #B5651E; }
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(120deg, #FFFFFF 0%, #F7F9FF 58%, #EEF3FF 100%);
  border: 1px solid var(--line); border-radius: 30px;
  padding: 40px 44px 36px; box-shadow: 0 28px 70px rgba(47, 99, 247, 0.1);
  margin-bottom: 18px;
}
.hero::after {
  content: ""; position: absolute; right: -90px; top: -120px;
  width: 320px; height: 320px; border-radius: 50%;
  background: radial-gradient(circle, rgba(47, 99, 247, 0.18), transparent 68%);
}
.hero-kicker {
  position: relative; color: var(--cobalt); font-size: 10px;
  font-weight: 800; letter-spacing: 0.24em; text-transform: uppercase;
}
.hero h1 {
  position: relative; margin: 14px 0 12px; max-width: 900px;
  color: var(--ink); font-size: clamp(2.5rem, 4.3vw, 4.4rem);
  font-weight: 900; line-height: 1.05; letter-spacing: -0.035em;
}
.hero p {
  position: relative; margin: 0 0 22px; max-width: 780px;
  color: #5F6572; font-size: 1.02rem;
}
.hero-chips { position: relative; display: flex; flex-wrap: wrap; gap: 8px; }
.period-chip {
  display: inline-flex; align-items: baseline; gap: 8px;
  background: #FFFFFF; border: 1px solid var(--line);
  border-radius: 999px; padding: 7px 12px; font-size: 11px;
  color: var(--muted); box-shadow: 0 5px 14px rgba(47, 99, 247, 0.04);
}
.period-chip strong {
  color: var(--cobalt); font-size: 10px; letter-spacing: 0.06em;
  text-transform: uppercase;
}
.metric-grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px; margin: 6px 0 22px;
}
.metric-card {
  position: relative; overflow: hidden; background: #FFFFFF;
  border: 1px solid var(--line); border-radius: 20px;
  padding: 19px 22px; box-shadow: 0 14px 28px rgba(47, 99, 247, 0.06);
}
.metric-card::before {
  content: ""; position: absolute; inset: 0 auto 0 0;
  width: 4px; background: var(--cobalt);
}
.metric-card.lavender::before { background: var(--lavender); }
.metric-card.mint::before { background: var(--mint); }
.metric-card.peach::before { background: var(--peach); }
.metric-value {
  color: var(--ink); font-family: var(--font-display);
  font-size: 2.15rem; font-weight: 900; line-height: 1;
}
.metric-label {
  margin-top: 9px; color: var(--muted); font-size: 10px;
  font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase;
}
.metric-hint { margin-top: 5px; color: #8A90A0; font-size: 11px; }
.insight-grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px; margin: 8px 0;
}
.insight-card { border: 1px solid var(--line); border-radius: 18px; padding: 17px 18px; }
.insight-blue { background: var(--blue-soft); border-color: var(--blue-line); }
.insight-mint { background: var(--mint-soft); border-color: #D4EFE5; }
.insight-lavender { background: var(--lavender-soft); border-color: #E5DAF7; }
.insight-peach { background: var(--peach-soft); border-color: #F7E0CD; }
.insight-card h4 { margin: 0 0 6px; color: var(--ink); font-size: 13px; }
.insight-card p { margin: 0; color: #5F6572; font-size: 12px; line-height: 1.55; }
.insight-dot {
  display: inline-block; width: 9px; height: 9px;
  margin-right: 7px; border-radius: 50%;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFFFF;
  border: 1px solid var(--line) !important;
  border-radius: 22px !important;
  box-shadow: 0 18px 38px rgba(47, 99, 247, 0.06);
  padding: 7px 9px 3px;
}
.accent {
  width: 58px; height: 4px; margin: 0 0 13px;
  border-radius: 999px; background: var(--cobalt);
}
.accent-violet { background: var(--lavender); }
.accent-amber { background: var(--peach); }
.accent-gray { background: #9AA1B2; }
.card-kicker {
  color: var(--muted); font-size: 9px; font-weight: 800;
  letter-spacing: 0.18em; text-transform: uppercase;
}
.card-title {
  margin: 6px 0 10px; color: var(--ink); font-family: var(--font-display);
  font-size: 1.38rem; font-weight: 900; line-height: 1.25;
}
.pill-row {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 6px; margin-bottom: 10px;
}
.pill {
  display: inline-flex; align-items: center; white-space: nowrap;
  border: 1px solid transparent; border-radius: 999px;
  padding: 4px 9px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.02em;
}
.pill-cobalt { background: var(--blue-soft); border-color: var(--blue-line); color: var(--cobalt); }
.pill-violet { background: var(--lavender-soft); border-color: #E5DAF7; color: #6841B4; }
.pill-amber { background: var(--peach-soft); border-color: #F7E0CD; color: #B5651E; }
.pill-green { background: var(--mint-soft); border-color: #D4EFE5; color: #1E7A5E; }
.pill-red { background: #FDECEE; border-color: #F7D6DB; color: #B73A4A; }
.pill-gray { background: var(--soft); border-color: var(--line); color: var(--muted); }
.card-note {
  margin-top: 10px; padding: 10px 12px; background: var(--soft);
  border-left: 3px solid var(--cobalt); border-radius: 8px;
  color: #5F6572; font-size: 11px; line-height: 1.55;
}
.card-note strong {
  color: var(--ink); font-size: 9px; letter-spacing: 0.12em;
  text-transform: uppercase;
}
.claim-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 9px 0; border-bottom: 1px solid #EFF1F6;
}
.claim-row:last-child { border-bottom: 0; }
.claim-text { color: var(--ink); font-size: 12.5px; line-height: 1.5; }
.claim-meta { margin-top: 4px; color: #8A90A0; font-size: 10px; }
.quote {
  margin: 4px 0 0; padding-left: 10px; border-left: 2px solid var(--blue-line);
  color: var(--muted); font-family: var(--font-display);
  font-size: 12px; font-style: italic; line-height: 1.5;
}
.coverage-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin: 8px 0 14px;
}
.coverage-card {
  background: #FFFFFF; border: 1px solid var(--line);
  border-radius: 18px; padding: 16px 18px;
  box-shadow: 0 10px 24px rgba(47, 99, 247, 0.04);
}
.coverage-platform {
  color: var(--muted); font-size: 10px; font-weight: 800;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.coverage-value {
  margin-top: 4px; color: var(--ink); font-family: var(--font-display);
  font-size: 1.8rem; font-weight: 900; line-height: 1;
}
.coverage-label { margin: 4px 0 10px; color: #8A90A0; font-size: 11px; }
[data-testid="stExpander"] {
  background: #FFFFFF !important;
  border: 1px solid var(--line) !important;
  border-radius: 16px !important;
  overflow: hidden;
}
[data-testid="stExpander"] details {
  background: transparent !important; border: 0 !important;
}
[data-testid="stExpander"] summary {
  background: #FFFFFF !important; color: var(--cobalt) !important;
  padding: 12px 16px !important; border-radius: 15px !important;
  font-weight: 600;
}
[data-testid="stExpander"] summary:hover {
  background: var(--blue-soft) !important;
}
[data-testid="stExpander"] summary svg,
[data-testid="stExpander"] [data-testid="stIconMaterial"] {
  color: var(--cobalt) !important;
}
[data-testid="stExpanderDetails"] { padding: 0 16px 14px !important; }
div[data-testid="stDataFrame"] {
  border: 1px solid var(--line); border-radius: 16px; overflow: hidden;
}
[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid var(--line);
  border-radius: 18px; padding: 16px;
}
[data-testid="stMetricValue"] {
  color: var(--cobalt); font-family: var(--font-display); font-weight: 900;
}
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"] { display: none; }
[data-testid="stToolbar"] { background: transparent; }
[data-testid="stTabs"] [role="tablist"] {
  gap: 6px; width: fit-content; padding: 6px;
  background: var(--soft); border: 1px solid var(--line);
  border-bottom: 1px solid var(--line) !important;
  border-radius: 999px; box-shadow: 0 12px 26px rgba(47, 99, 247, 0.06);
}
[data-testid="stTab"] {
  min-height: 0; padding: 10px 20px !important;
  border: 0 !important; border-radius: 999px !important;
  color: var(--ink) !important; background: transparent !important;
  font-weight: 600; transition: background 0.18s ease, color 0.18s ease;
}
[data-testid="stTab"]:hover {
  background: #FFFFFF !important; color: var(--cobalt) !important;
}
[data-testid="stTab"][aria-selected="true"] {
  background: var(--cobalt) !important;
  color: #FFFFFF !important;
  box-shadow: 0 9px 20px rgba(47, 99, 247, 0.24);
}
[data-testid="stTab"] [data-testid="stMarkdownContainer"] p {
  color: inherit !important; font-weight: 600;
}
[data-testid="stTab"] .react-aria-SelectionIndicator { display: none !important; }
[data-testid="stBaseButton-elementToolbar"] {
  border-radius: 9px !important; color: var(--cobalt) !important;
}
[data-testid="stBaseButton-elementToolbar"]:hover {
  background: var(--blue-soft) !important;
}
[data-testid="stBaseButton-primary"] {
  background: var(--cobalt) !important; border: 0 !important;
  border-radius: 999px !important; color: #FFFFFF !important;
}
[data-testid="stBaseButton-secondary"] {
  background: #FFFFFF !important; border: 1px solid var(--line) !important;
  border-radius: 999px !important; color: var(--cobalt) !important;
}
[data-testid="stSelectbox"] .react-aria-ComboBox > div {
  background: #FFFFFF !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
[data-testid="stSelectbox"] .react-aria-ComboBox > div:hover {
  border-color: var(--cobalt) !important;
}
[data-testid="stSelectbox"] .react-aria-ComboBox:focus-within > div {
  border-color: var(--cobalt) !important;
  box-shadow: 0 0 0 3px rgba(47, 99, 247, 0.12) !important;
}
[data-testid="stSelectbox"] input {
  background: transparent !important; color: var(--ink) !important;
}
[data-testid="stSelectbox"] button { color: var(--cobalt) !important; }
[data-testid="stSelectbox"] label p {
  color: var(--ink) !important; font-weight: 600;
}
[role="listbox"] {
  background: #FFFFFF !important; border: 1px solid var(--line) !important;
  border-radius: 14px !important; padding: 6px !important;
  box-shadow: 0 18px 40px rgba(47, 99, 247, 0.14) !important;
}
[role="option"] { border-radius: 10px !important; }
[role="option"]:hover { background: var(--blue-soft) !important; }
[role="option"][aria-selected="true"] {
  background: var(--blue-soft) !important; color: var(--cobalt) !important;
}
[data-testid="stAlert"] {
  background: #FFFFFF !important; border: 1px solid var(--line) !important;
  border-radius: 14px !important;
}
[data-testid="stAlert"] p { color: var(--ink); }
[data-testid="stTab"]:focus-visible,
button:focus-visible {
  outline: 2px solid rgba(47, 99, 247, 0.35);
  outline-offset: 2px;
}
@media (max-width: 1100px) {
  .metric-grid, .insight-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero { padding: 30px 26px; }
}
@media (max-width: 640px) {
  .metric-grid, .insight-grid { grid-template-columns: 1fr; }
  .hero h1 { font-size: 2.4rem; }
}
</style>
"""


def inject_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def _esc(value):
    return html.escape(str(value), quote=True)


def _pill(label, tone="gray"):
    return f'<span class="pill pill-{tone}">{_esc(label)}</span>'


def _status_pill(status):
    return _pill(status, STATUS_TONES.get(status, "gray"))


def _claim_pill(status):
    return _pill(status, CLAIM_TONES.get(status, "gray"))


def _side_pill(label, tone):
    return f'<span class="side-pill side-pill-{tone}">{_esc(label)}</span>'


def _style_fig(fig, height=None):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Segoe UI, system-ui, sans-serif",
            color="#4B5565",
            size=12,
        ),
        title=dict(
            font=dict(family="Georgia, serif", color="#172033", size=19),
            x=0,
            xanchor="left",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=8, r=8, t=54, b=8),
        hoverlabel=dict(
            bgcolor="#FFFDF9",
            bordercolor="#E5DCCD",
            font=dict(family="Segoe UI, sans-serif", color="#172033"),
        ),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#EEE7DC", zeroline=False,
        linecolor="#E5DCCD", tickfont=dict(size=11),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#EEE7DC", zeroline=False,
        linecolor="#E5DCCD", tickfont=dict(size=11),
    )
    if height:
        fig.update_layout(height=height)
    return fig


st.set_page_config(page_title="Intelligence Hub", layout="wide")
inject_css()


@st.cache_data(show_spinner=False)
def load_data(mode):
    with closing(sqlite3.connect(DB)) as con:
        real_signals = pd.read_sql_query(
            "SELECT * FROM signals ORDER BY signal_type, status, title", con
        )
        real_evidence = pd.read_sql_query(
            "SELECT * FROM signal_evidence ORDER BY signal_id, evidence_type, evidence_id",
            con,
        )
        real_briefs = pd.read_sql_query(
            "SELECT * FROM briefs ORDER BY created_at, brief_id", con
        )
        real_claims = pd.read_sql_query(
            "SELECT * FROM claims ORDER BY created_at, claim_id", con
        )
        real_coverage = pd.read_sql_query(
            "SELECT * FROM social_coverage ORDER BY brand, platform", con
        )
        real_social = pd.read_sql_query("SELECT * FROM social_posts", con)
        baseline, current = pricing.load_pricing(con)
        cf = pd.read_sql_query("SELECT * FROM cf_performance", con)
        markets = pd.read_sql_query("SELECT * FROM klytics_markets", con)

    real_theme_labels = pd.read_csv(
        DATA / "theme_labels.csv", dtype=str, keep_default_na=False
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


def render_sidebar(data):
    periods = "".join(
        f'<div class="side-period">'
        f'<div class="side-period-label">{_esc(label)}</div>'
        f'<div class="side-period-value">{_esc(value)}</div>'
        f"</div>"
        for label, value in _period_rows(data)
    )
    refreshed = pd.to_datetime(
        data["signals"]["created_at"], errors="coerce", utc=True
    ).max()
    refreshed_text = "n/a" if pd.isna(refreshed) else f"{refreshed:%Y-%m-%d %H:%M} UTC"

    with st.sidebar:
        st.markdown(
            f"""
            <div class="brand">
              <div class="brand-mark" aria-hidden="true">
                <span class="wing wing-left"></span>
                <span class="wing wing-right"></span>
              </div>
              <div>
                <div class="brand-eyebrow">Intelligence Hub</div>
                <div class="brand-title">Cobalt Fairy</div>
              </div>
            </div>
            <div class="side-section">
              <div class="side-label">Data periods</div>
              {periods}
            </div>
            <div class="side-section">
              <div class="side-label">Status legend</div>
              {_side_pill("candidate", "cobalt")}
              {_side_pill("inferential", "violet")}
              {_side_pill("insufficient", "amber")}
            </div>
            <div class="side-note">
              Signals generated {_esc(refreshed_text)}.<br>
              {_esc('Synthetic social + cross-source fixture; CF/pricing real. Not real evidence.' if data['mode'] == 'synthetic' else 'Read-only prototype. Cached AI output only; no live AI calls.')}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_hero(data):
    chips = "".join(
        f'<span class="period-chip"><strong>{_esc(label)}</strong>'
        f"{_esc(value)}</span>"
        for label, value in _period_rows(data)
    )
    mode_label = (
        "Synthetic social demo"
        if data["mode"] == "synthetic"
        else "Real social data"
    )
    chips += (
        f'<span class="period-chip"><strong>Mode</strong>'
        f"{_esc(mode_label)}</span>"
    )
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-kicker">Cobalt Fairy · Market & Competitive Intelligence</div>
          <h1>Signals worth your attention.</h1>
          <p>
            An evidence-first view of Cobalt Fairy's portfolio and FairyMail's
            competitive landscape. See what changed, why it matters, and exactly
            which source supports it.
          </p>
          <div class="hero-chips">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(data):
    signals = data["signals"]
    claims = data["claims"]
    reviewable = signals[signals["status"].isin(["candidate", "inferential"])]
    verified = int((claims["verification_status"] == "verified").sum())
    gaps = int(data["coverage"]["status"].ne("complete").sum())
    claim_label = (
        "Claims checked"
        if data["mode"] == "synthetic"
        else "AI claims verified"
    )
    claim_hint = (
        "fixture + real pricing/CF"
        if data["mode"] == "synthetic"
        else "exact evidence check"
    )
    cross_hint = (
        "synthetic co-occurrence"
        if data["mode"] == "synthetic"
        else "multi-source co-occurrence"
    )
    items = [
        (len(reviewable), "Signals to review", "candidate + inferential", "cobalt"),
        (cross_count, "Cross-source patterns", cross_hint, "gold"),
        (f"{verified}/{len(claims)}", claim_label, claim_hint, "green"),
        (gaps, "Coverage caveats", "captured source limits", "amber"),
    ]
    cards = "".join(
        f'<div class="metric-card {tone}">'
        f'<div class="metric-value">{_esc(value)}</div>'
        f'<div class="metric-label">{_esc(label)}</div>'
        f'<div class="metric-hint">{_esc(hint)}</div>'
        f"</div>"
        for value, label, hint, tone in items
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def render_insight_cards():
    items = [
        ("Observed", "Quotes and price points captured directly from sources.", "blue", "#2F63F7"),
        ("Calculated", "Deterministic metrics such as units/day, price gaps and mapping confidence.", "mint", "#2E9B7A"),
        ("AI-assisted", "Cached theme labels and positioning briefs, checked against cited evidence.", "lavender", "#7C5CBF"),
        ("Insufficient", "Below the evidence threshold and never presented as a trend.", "peach", "#F0A05A"),
    ]
    cards = "".join(
        f'<div class="insight-card insight-{tone}">'
        f'<h4><span class="insight-dot" style="background:{color}"></span>{_esc(title)}</h4>'
        f"<p>{_esc(text)}</p>"
        f"</div>"
        for title, text, tone, color in items
    )
    st.markdown(f'<div class="insight-grid">{cards}</div>', unsafe_allow_html=True)


def render_coverage_cards(data):
    coverage = data["coverage"].copy()
    coverage["posts_captured"] = pd.to_numeric(
        coverage["posts_captured"], errors="coerce"
    ).fillna(0)
    groups = coverage.groupby("platform", as_index=False).agg(
        posts=("posts_captured", "sum"),
        statuses=("status", lambda values: ", ".join(
            sorted({str(value) for value in values})
        )),
    )
    cards = []
    for row in groups.itertuples(index=False):
        tone = "green" if row.statuses == "complete" else "amber"
        cards.append(
            f'<div class="coverage-card">'
            f'<div class="coverage-platform">{_esc(row.platform)}</div>'
            f'<div class="coverage-value">{int(row.posts)}</div>'
            f'<div class="coverage-label">posts captured</div>'
            f'<div class="pill-row">{_pill(row.statuses, tone)}</div>'
            f"</div>"
        )
    st.markdown(
        f'<div class="coverage-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _confidence(value):
    number = pd.to_numeric(value, errors="coerce")
    return "n/a" if pd.isna(number) else f"{number:.2f}"


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


def _signal_view(signals):
    view = signals.copy()
    view["period"] = [
        _period(start, end)
        for start, end in zip(view["period_start"], view["period_end"])
    ]
    view["confidence"] = pd.to_numeric(view["confidence"], errors="coerce").round(2)
    return view[[
        "title", "entity", "period", "status", "confidence", "coverage_note",
    ]]


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
        f"{row['price_gap_pct']:+.1f}%; mapping confidence "
        f"{row['confidence']:.2f}."
    )


def show_signals(signals, evidence, key):
    if signals.empty:
        st.info("No signals for this view.")
        return

    st.dataframe(
        _signal_view(signals),
        hide_index=True,
        width="stretch",
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "confidence", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )

    options = {
        f"{row.title} · {row.signal_id}": row.signal_id
        for row in signals.itertuples(index=False)
    }
    with st.expander("Evidence drill-down"):
        selected = st.selectbox("Signal", list(options), key=f"{key}_signal")
        rows = evidence[evidence["signal_id"] == options[selected]]
        if rows.empty:
            st.info("No signal_evidence rows for this signal.")
        else:
            st.dataframe(
                rows[["evidence_type", "role", "quote", "verified", "evidence_id"]],
                hide_index=True,
                width="stretch",
            )


def render_claim_rows(claims):
    if claims.empty:
        st.caption("No verified or inferential claims.")
        return

    rows = []
    for claim in claims.itertuples(index=False):
        quote_html = ""
        if isinstance(claim.quote, str) and claim.quote.strip():
            quote_html = f'<div class="quote">“{_esc(claim.quote)}”</div>'
        rows.append(
            f'<div class="claim-row">'
            f'{_claim_pill(claim.verification_status)}'
            f"<div>"
            f'<div class="claim-text">{_esc(claim.claim_text)}</div>'
            f"{quote_html}"
            f'<div class="claim-meta">evidence {_esc(claim.evidence_ids)}</div>'
            f"</div></div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def render_signal_card(signal, data):
    tone = STATUS_TONES.get(signal.status, "gray")
    with st.container(border=True):
        st.markdown(
            f'<div class="accent accent-{tone}"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="card-kicker">'
            f'{_esc(signal.signal_type.replace("_", " "))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="card-title">{_esc(signal.title)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="pill-row">'
            f"{_status_pill(signal.status)}"
            f'{_pill("confidence " + _confidence(signal.confidence), "gray")}'
            f'{_pill(_period(signal.period_start, signal.period_end), "gray")}'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write(signal.summary)
        st.markdown(
            f'<div class="card-note"><strong>Coverage</strong><br>'
            f"{_esc(signal.coverage_note)}</div>",
            unsafe_allow_html=True,
        )

        evidence = data["evidence"]
        briefs = data["briefs"]
        evidence_rows = evidence[evidence["signal_id"] == signal.signal_id]
        brief = briefs[briefs["signal_id"] == signal.signal_id]
        if evidence_rows.empty and brief.empty:
            st.caption("No cached evidence or AI interpretation.")
            return

        with st.expander("Evidence and AI interpretation"):
            st.markdown(
                '<div class="card-kicker">Source evidence</div>',
                unsafe_allow_html=True,
            )
            if evidence_rows.empty:
                st.caption("No signal_evidence rows.")
            else:
                st.dataframe(
                    evidence_rows[["evidence_type", "quote", "verified"]],
                    hide_index=True,
                    width="stretch",
                )

            is_fixture = (
                data["mode"] == "synthetic"
                and str(signal.signal_id).startswith("syn-")
            )
            interpretation_label = (
                "Fixture interpretation" if is_fixture else "AI interpretation"
            )
            source_pill = "synthetic" if is_fixture else "cached"
            st.markdown(
                f'<div class="pill-row" style="margin-top:14px;">'
                f'{_pill(interpretation_label, "violet")}'
                f'{_pill(source_pill, "gray")}</div>',
                unsafe_allow_html=True,
            )
            if brief.empty:
                st.caption("No cached brief for this signal.")
                return

            item = brief.iloc[0]
            st.write(item["positioning"])
            st.caption(
                f"model {item['model']} · prompt {item['prompt_version']} · "
                f"cached {item['created_at']} · checker {item['checker_status']}"
            )

            claims = data["claims"]
            claim_rows = claims[
                (claims["brief_id"] == item["brief_id"])
                & (claims["verification_status"] != "unsupported")
            ]
            render_claim_rows(claim_rows)


def render_briefs(data):
    briefs = data["briefs"].merge(
        data["signals"][["signal_id", "title", "signal_type", "status"]],
        on="signal_id",
        how="left",
    )
    if briefs.empty:
        st.info("No cached briefs available.")
        return

    options = {
        f"{row.title} · {row.signal_type} · {row.brief_id}": row.brief_id
        for row in briefs.itertuples(index=False)
    }
    selected = st.selectbox("Cached brief", list(options), key="brief_select")
    brief = briefs[briefs["brief_id"] == options[selected]].iloc[0]

    is_fixture = brief["model"] == "synthetic_fixture"
    interpretation_label = (
        "Fixture interpretation" if is_fixture else "AI interpretation"
    )
    source_pill = "synthetic" if is_fixture else "cached"
    st.markdown(
        f'<div class="pill-row">'
        f'{_pill(interpretation_label, "violet")}'
        f'{_pill(source_pill, "gray")}'
        f'{_pill(brief["signal_type"], "gray")}'
        f'{_status_pill(brief["status"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="card-title">{_esc(brief["title"])}</div>',
        unsafe_allow_html=True,
    )
    st.write(brief["positioning"])
    st.caption(
        f"model {brief['model']} · prompt {brief['prompt_version']} · "
        f"checker {brief['checker_status']} · cached {brief['created_at']} · "
        f"signal status {brief['status']}"
    )

    claims = data["claims"]
    visible = claims[
        (claims["brief_id"] == brief["brief_id"])
        & (claims["verification_status"] != "unsupported")
    ]
    render_claim_rows(visible)


def render_inference_queue(data):
    claims = data["claims"]
    inferential = claims[claims["verification_status"] == "inferential"]
    st.caption(
        "Inferential claims are AI statements without an exact supporting quote. "
        "They remain visible with a badge and require human review."
    )
    if inferential.empty:
        st.success("No inferential claims.")
        return
    rows = inferential.merge(
        data["signals"][["signal_id", "title"]], on="signal_id", how="left"
    )
    st.dataframe(
        rows[[
            "title", "claim_text", "checker_note", "evidence_ids", "created_at",
        ]],
        hide_index=True,
        width="stretch",
    )


def render_theme_audit(data):
    labels = data["theme_labels"].copy()
    if labels.empty:
        st.info("No cached theme labels available.")
        return
    labels["confidence"] = pd.to_numeric(labels["confidence"], errors="coerce").round(2)
    label_source = (
        "synthetic fixture labels"
        if data["mode"] == "synthetic"
        else "cached labels"
    )
    st.caption(
        f"{len(labels)} {label_source} across {labels['post_id'].nunique()} posts. "
        "Every label stores an exact quote copied from the post."
    )
    st.dataframe(
        labels[[
            "post_id", "theme_id", "confidence", "evidence_quote", "label_source",
            "model", "prompt_version", "created_at",
        ]],
        hide_index=True,
        width="stretch",
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "confidence", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )


def render_error_log(data):
    claims = data["claims"]
    unsupported = claims[claims["verification_status"] == "unsupported"]
    issues = data["issues"]

    st.subheader("Error log")
    st.caption(
        "Unsupported claims are shown only here and are excluded from the "
        "brief claim badges."
    )
    with st.expander(
        f"Unsupported claims ({len(unsupported)})", expanded=not unsupported.empty
    ):
        if unsupported.empty:
            st.success("No unsupported claims.")
        else:
            rows = unsupported.merge(
                data["signals"][["signal_id", "title"]],
                on="signal_id",
                how="left",
            )
            st.dataframe(
                rows[[
                    "title", "claim_text", "checker_note", "evidence_ids",
                    "created_at",
                ]],
                hide_index=True,
                width="stretch",
            )

    with st.expander(f"Mapping issues ({len(issues)})", expanded=not issues.empty):
        if issues.empty:
            st.success("No mapping issues.")
        else:
            st.dataframe(issues, hide_index=True, width="stretch")


if "use_real_social" not in st.session_state:
    st.session_state.use_real_social = False

source_left, source_right = st.columns([8, 2])
with source_left:
    st.caption(
        "Synthetic social demo"
        if not st.session_state.use_real_social
        else "Real social data"
    )
with source_right:
    button_label = (
        "Use real social data"
        if not st.session_state.use_real_social
        else "Use synthetic demo"
    )
    if st.button(
        button_label,
        use_container_width=True,
        key="toggle_social_data",
        type="primary" if not st.session_state.use_real_social else "secondary",
    ):
        st.session_state.use_real_social = not st.session_state.use_real_social
        st.rerun()

mode = "real" if st.session_state.use_real_social else "synthetic"
data = load_data(mode)
signals = data["signals"]
evidence = data["evidence"]

render_sidebar(data)
render_hero(data)
if mode == "synthetic":
    st.warning(
        "SYNTHETIC SOCIAL DEMO — fictional brands, posts, and cross-source "
        "pricing. CF and pricing comparison panels use real captured data. "
        "Not real competitor evidence."
    )
else:
    st.success(
        "Real data mode — 11 captured public Facebook posts with coverage gaps."
    )
render_metric_cards(data)

overview_tab, cf_tab, fairy_tab, evidence_tab = st.tabs(
    ["Overview", "Cobalt Fairy", "FairyMail", "Evidence"]
)

with overview_tab:
    st.subheader("How to read this hub")
    render_insight_cards()

    st.subheader("Key findings to review")
    st.caption(
        "Highest-priority signal per source type. Candidate and inferential "
        "signals need human review; insufficient signals are downgraded."
    )
    for row in _top_per_type(signals, 1).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Cross-source relationships")
    cross = signals[signals["signal_type"] == "cross_source"]
    for row in _prioritized(cross).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("AI-assisted layer")
    claims = data["claims"]
    ai_metrics = st.columns(4)
    ai_metrics[0].metric("Theme labels", len(data["theme_labels"]))
    ai_metrics[1].metric("Cached briefs", len(data["briefs"]))
    ai_metrics[2].metric(
        "Verified claims",
        int((claims["verification_status"] == "verified").sum()),
    )
    ai_metrics[3].metric(
        "Inferential claims",
        int((claims["verification_status"] == "inferential").sum()),
    )
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic social and cross-source labels/briefs are fixture-generated; "
            "pricing and CF briefs remain cached AI output. "
            "Switch to real data for the full AI layer."
        )
    else:
        st.caption(
            "The AI-assisted layer is theme extraction over social posts plus cached "
            "positioning briefs. Every theme label must quote the post. Brief claims "
            "are checked against cited evidence IDs; unsupported claims are isolated "
            "in the Evidence tab's error log."
        )

    st.subheader("Uncertainty cases")
    uncertain = _uncertain(signals)
    st.caption(
        f"Insufficient evidence or confidence below {LOW_CONFIDENCE:.2f}. "
        "These stay visible but are not promoted as findings."
    )
    if uncertain.empty:
        st.success("No uncertainty cases flagged.")
    else:
        st.dataframe(
            _signal_view(uncertain),
            hide_index=True,
            width="stretch",
            column_config={
                "confidence": st.column_config.ProgressColumn(
                    "confidence", min_value=0.0, max_value=1.0, format="%.2f"
                ),
            },
        )

    st.subheader("Signal register")
    with st.expander("Browse all signals"):
        show_signals(signals, evidence, "overview")

with cf_tab:
    st.subheader("Market vs portfolio")
    st.caption(
        f"Commercial and market months: {_month_range(data['cf']['month'])}. "
        "Mapping confidence comes from data/mappings.csv."
    )

    findings = _cf_findings(data["summary"], data["same_title"])
    comparable = findings[
        (findings["same_title_n"] >= 5)
        & findings["market_growth_pct"].notna()
        & findings["same_title_units_change_pct"].notna()
    ] if not findings.empty else findings
    if comparable.empty:
        st.info("No comparable mapped metrics available.")
    else:
        fig = px.scatter(
            comparable,
            x="market_growth_pct",
            y="same_title_units_change_pct",
            color="quadrant",
            color_discrete_map=CF_COLORS,
            symbol="relationship",
            size="titles",
            size_max=34,
            hover_data={
                "source_label": True,
                "target_path": True,
                "price_gap_pct": ":.1f",
                "confidence": ":.2f",
                "same_title_n": True,
            },
            labels={
                "market_growth_pct": "Market growth (%)",
                "same_title_units_change_pct": "CF same-title units/day change (%)",
                "quadrant": "Relative position",
                "relationship": "Mapping",
            },
            title="CF performance relative to market conditions",
        )
        fig.update_traces(
            marker=dict(line=dict(width=1, color="#FFFDF9"))
        )
        fig.add_vline(x=0, line_dash="dash", line_color="#BCB3A3", line_width=1)
        fig.add_hline(y=0, line_dash="dash", line_color="#BCB3A3", line_width=1)
        st.plotly_chart(
            _style_fig(fig, 430),
            width="stretch",
            config={"displayModeBar": False},
        )
        st.caption(
            "Only mappings with at least 5 same-title observations are charted. "
            "Thin or low-confidence mappings are handled in Uncertainty."
        )

        primary = comparable[comparable["relationship"] == "primary"]
        headline = primary if not primary.empty else comparable
        strongest = headline.sort_values("relative_units_gap").iloc[-1]
        weakest = headline.sort_values("relative_units_gap").iloc[0]
        st.markdown(f"- **Strongest relative performance:** {_finding_sentence(strongest)}")
        st.markdown(f"- **Weakest relative performance:** {_finding_sentence(weakest)}")

    if not findings.empty:
        table = findings[[
            "source_label", "relationship", "quadrant", "same_title_n",
            "same_title_units_change_pct", "market_growth_pct",
            "relative_units_gap", "price_gap_pct", "confidence",
            "insufficient_titles",
        ]].copy()
        for column in [
            "same_title_units_change_pct", "market_growth_pct",
            "relative_units_gap", "price_gap_pct", "confidence",
        ]:
            table[column] = pd.to_numeric(table[column], errors="coerce").round(2)
        st.dataframe(table, hide_index=True, width="stretch")

    st.subheader("CF signals")
    cf_signals = signals[signals["signal_type"] == "cf_market"]
    for row in _prioritized(cf_signals).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Mapping confidence and ambiguity")
    mappings = data["mappings"].copy()
    mappings["confidence"] = pd.to_numeric(
        mappings["confidence"], errors="coerce"
    ).round(2)
    st.dataframe(
        mappings[[
            "source_label", "target_path", "relationship", "confidence",
            "review_status", "method", "rationale",
        ]].sort_values("confidence"),
        hide_index=True,
        width="stretch",
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "confidence", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )

    st.subheader("Uncertainty handling")
    cf_uncertain = _uncertain(cf_signals)
    st.caption(
        "Ambiguous or low-confidence mappings are flagged rather than silently "
        "treated as equivalent categories."
    )
    if cf_uncertain.empty:
        st.success("No low-confidence or insufficient CF signals.")
    else:
        for row in _prioritized(cf_uncertain).itertuples(index=False):
            render_signal_card(row, data)

with fairy_tab:
    st.subheader("Competitive change feed")
    interpretation_label = (
        "Fixture interpretation"
        if data["mode"] == "synthetic"
        else "AI interpretation"
    )
    st.caption(
        "Pricing and social signals are ranked by status and confidence. "
        f"{interpretation_label} is shown only with its source evidence."
    )
    fairy_signals = signals[
        signals["signal_type"].isin(["pricing_change", "social_theme"])
    ]
    for row in _top_per_type(fairy_signals, 2).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Cross-source context")
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic cross-source demo: fictional brands, synthetic pricing, "
            "and synthetic posts. Not real competitor evidence."
        )
    cross = signals[signals["signal_type"] == "cross_source"]
    for row in _prioritized(cross).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Pricing comparison")
    changes = data["pricing_changes"].copy()
    for column in ["baseline_price", "price", "price_change", "price_change_pct"]:
        changes[column] = pd.to_numeric(changes[column], errors="coerce").round(2)
    with st.expander("Baseline vs current pricing", expanded=True):
        st.dataframe(
            changes[[
                "platform", "plan", "baseline_plan", "baseline_tier",
                "current_tier", "tier_basis", "baseline_price", "price",
                "price_change_pct", "change_type", "plan_renamed",
                "tier_mismatch", "captured_at", "source_url",
            ]],
            hide_index=True,
            width="stretch",
            column_config={
                "source_url": st.column_config.LinkColumn("source", display_text="link"),
            },
        )

        changed = changes[
            changes["change_type"].isin(["price_change", "new_plan"])
            | changes["plan_renamed"]
        ]
        if not changed.empty:
            fig = px.bar(
                changed,
                x="price_change_pct",
                y="plan",
                orientation="h",
                color="platform",
                color_discrete_sequence=PLATFORM_COLORS,
                barmode="group",
                hover_data=[
                    "baseline_plan", "baseline_price", "price", "current_tier",
                    "tier_basis",
                ],
                labels={"price_change_pct": "Price change (%)", "plan": "Plan"},
                title="Captured monthly price change by plan",
            )
            st.plotly_chart(
                _style_fig(fig, 360),
                width="stretch",
                config={"displayModeBar": False},
            )

    st.subheader("Social theme signals")
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic social demo — fictional brands and posts. "
            "Pricing comparison data is real; cross-source demo uses synthetic pricing."
        )
    social_signals = signals[signals["signal_type"] == "social_theme"]
    for row in _top_per_type(social_signals, 3).itertuples(index=False):
        render_signal_card(row, data)
    with st.expander("All social theme signals"):
        show_signals(social_signals, evidence, "social")

    st.subheader("Social coverage gaps")
    coverage = data["coverage"].copy()
    coverage_label = (
        "Synthetic coverage window"
        if data["mode"] == "synthetic"
        else "Coverage window"
    )
    st.caption(
        f"{coverage_label}: "
        f"{_span(coverage['window_start'], coverage['window_end'])}. "
        "Gaps are reported as captured, not inferred."
    )
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic fixture includes LinkedIn posts in all three months; "
            "the real capture remains Facebook-only."
        )
    render_coverage_cards(data)
    with st.expander("Coverage details"):
        st.dataframe(
            coverage[[
                "brand", "platform", "status", "posts_captured", "window_start",
                "window_end", "captured_at", "notes",
            ]],
            hide_index=True,
            width="stretch",
        )

    st.subheader("Uncertainty handling")
    fairy_uncertain = _uncertain(
        signals[signals["signal_type"].isin(
            ["pricing_change", "social_theme", "cross_source"]
        )]
    )
    st.caption(
        "Isolated posts, low-confidence signals and coverage gaps are kept "
        "separate from candidate findings."
    )
    if fairy_uncertain.empty:
        st.success("No low-confidence or insufficient FairyMail signals.")
    else:
        for row in _prioritized(fairy_uncertain).itertuples(index=False):
            render_signal_card(row, data)

with evidence_tab:
    st.subheader("AI-assisted outputs")
    st.caption(
        "Verified and inferential claims are badged. Unsupported claims are "
        "shown only in the error log."
    )
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic social and cross-source labels/briefs are fixture-generated; "
            "real pricing and CF briefs are cached AI output. "
            "Synthetic posts and pricing are not real competitor evidence."
        )
    render_briefs(data)

    st.divider()
    st.subheader("AI review queue")
    render_inference_queue(data)

    st.divider()
    st.subheader("Theme labeling audit")
    render_theme_audit(data)

    st.divider()
    st.subheader("Signal evidence drill-down")
    show_signals(signals, evidence, "evidence")

    st.divider()
    render_error_log(data)
