import streamlit as st

from ..components import (
    render_briefs,
    render_error_log,
    render_inference_queue,
    render_theme_audit,
    show_signals,
)


def render_evidence(data):
    signals = data["signals"]
    evidence = data["evidence"]

    st.subheader("AI outputs and checks")
    st.caption(
        "Each claim shows whether it has an exact source quote or needs review. "
        "Unsupported claims are shown only in the error log."
    )
    if data["mode"] == "synthetic":
        st.caption(
            "Synthetic social and cross-source labels/briefs are fixture-generated; "
            "real pricing and CF briefs are cached AI output. "
            "Synthetic posts and pricing are not real competitor evidence."
        )
    render_briefs(data)

    st.divider()
    st.subheader("Claims needing review")
    render_inference_queue(data)

    st.divider()
    st.subheader("Theme labels")
    render_theme_audit(data)

    st.divider()
    st.subheader("Source evidence")
    show_signals(signals, evidence, "evidence")

    st.divider()
    render_error_log(data)
