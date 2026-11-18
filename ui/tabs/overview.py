import streamlit as st

from ..components import _signal_view, render_signal_card
from ..data import _prioritized, _top_per_type, _uncertain


def render_overview(data):
    signals = data["signals"]

    st.subheader("Key findings to review")
    st.caption(
        "Highest-priority signal per source type, sorted for review. "
        "Low-evidence items stay in the uncertainty list."
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
        "Claims with source quote",
        int((claims["verification_status"] == "verified").sum()),
    )
    ai_metrics[3].metric(
        "Claims needing review",
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
            "AI helps label social themes and draft positioning briefs. "
            "Every theme label must quote the post; claims are checked against the "
            "cited source. Unsupported claims are isolated in the Evidence tab."
        )

    st.subheader("Uncertainty cases")
    uncertain = _uncertain(signals)
    st.caption(
        "These items have low evidence strength or too little evidence. "
        "They stay visible but are not promoted as findings."
    )
    if uncertain.empty:
        st.success("No uncertainty cases flagged.")
    else:
        st.dataframe(
            _signal_view(uncertain),
            hide_index=True,
            width="stretch",
        )
