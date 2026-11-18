import html

import pandas as pd
import streamlit as st

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
STATUS_LABELS = {
    "candidate": "Needs review",
    "inferential": "Suggested link",
    "insufficient": "Not enough evidence",
}
SIGNAL_LABELS = {
    "cf_market": "CF vs market",
    "cross_source": "Cross-source",
    "pricing_change": "Pricing change",
    "social_theme": "Social theme",
}
EVIDENCE_LABELS = {
    "social_post": "Social post",
    "pricing_current": "Current pricing",
    "pricing_baseline": "Baseline pricing",
    "klytics_market": "Market report",
    "mapping": "Taxonomy mapping",
    "cf_performance": "CF performance",
}
CLAIM_LABELS = {
    "verified": "Source quote",
    "inferential": "Inference",
    "unsupported": "Unsupported",
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
.legend-block { margin: 0 0 16px; }
.legend-block:last-child { margin-bottom: 4px; }
.legend-heading {
  color: var(--muted); font-size: 9px; font-weight: 800;
  letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 9px;
}
.legend-item {
  display: flex; align-items: baseline; gap: 9px; margin-bottom: 8px;
}
.legend-item:last-child { margin-bottom: 0; }
.legend-item .pill { flex: 0 0 auto; }
.legend-desc {
  color: #5F6572; font-size: 11px; line-height: 1.45;
}
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
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero { padding: 30px 26px; }
}
@media (max-width: 640px) {
  .metric-grid { grid-template-columns: 1fr; }
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


def _status_label(status):
    return STATUS_LABELS.get(status, str(status).replace("_", " ").title())


def _signal_label(signal_type):
    return SIGNAL_LABELS.get(
        signal_type, str(signal_type).replace("_", " ").title()
    )


def _confidence_label(value):
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "n/a"
    if number >= 0.85:
        return "High"
    if number >= LOW_CONFIDENCE:
        return "Medium"
    return "Low"


def _evidence_label(evidence_type):
    return EVIDENCE_LABELS.get(
        evidence_type, str(evidence_type).replace("_", " ").title()
    )


def _status_pill(status):
    return _pill(_status_label(status), STATUS_TONES.get(status, "gray"))


def _claim_pill(status):
    return _pill(CLAIM_LABELS.get(status, status), CLAIM_TONES.get(status, "gray"))


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
            x=1,
            xanchor="right",
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
