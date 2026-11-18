import streamlit as st

from ui.components import render_hero, render_metric_cards, render_sidebar
from ui.data import load_data
from ui.tabs.cobalt_fairy import render_cobalt_fairy
from ui.tabs.evidence import render_evidence
from ui.tabs.fairymail import render_fairymail
from ui.tabs.overview import render_overview
from ui.theme import inject_css

st.set_page_config(page_title="Intelligence Hub", layout="wide")
inject_css()

data = load_data("real")
if data.get("error"):
    st.error(
        data["error"]
        + " Run ingest.py, signals.py, and briefs.py to initialize the dashboard."
    )
    st.stop()

render_sidebar(data)
render_hero(data)
render_metric_cards(data)

overview_tab, cf_tab, fairy_tab, evidence_tab = st.tabs(
    ["Overview", "Cobalt Fairy", "FairyMail", "Evidence"]
)

with overview_tab:
    render_overview(data)

with cf_tab:
    render_cobalt_fairy(data)

with fairy_tab:
    render_fairymail(data)

with evidence_tab:
    render_evidence(data)
