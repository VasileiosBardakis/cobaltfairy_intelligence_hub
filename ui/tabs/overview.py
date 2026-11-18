import streamlit as st

from ..components import _signal_view, render_signal_card
from ..data import _prioritized, _top_per_type, _uncertain


def render_overview(data):
    signals = data["signals"]

    st.subheader("Key findings to review")
    st.caption(
        "Highest-priority CF, pricing and social signal, sorted for review. "
        "Cross-source relationships follow separately. Low-evidence items stay "
        "in the uncertainty list."
    )
    primary = signals[signals["signal_type"] != "cross_source"]
    for row in _top_per_type(primary, 1).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Cross-source relationships")
    cross = signals[signals["signal_type"] == "cross_source"]
    for row in _prioritized(cross).itertuples(index=False):
        render_signal_card(row, data)

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
