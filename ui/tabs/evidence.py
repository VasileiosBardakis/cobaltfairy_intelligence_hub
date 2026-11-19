import streamlit as st

from ..components import (
    render_all_signals,
    render_briefs,
    render_claims_audit,
    render_error_log,
    render_inference_queue,
    render_theme_audit,
)


def render_evidence(data):
    st.subheader("AI outputs and checks")
    st.caption(
        "Each claim shows whether it has an exact source quote or needs review. "
        "Unsupported claims are shown only in the error log."
    )
    render_briefs(data)

    st.divider()
    st.subheader("Needs review")
    render_inference_queue(data)

    st.divider()
    st.subheader("All claims")
    render_claims_audit(data)

    st.divider()
    st.subheader("Theme labels")
    render_theme_audit(data)

    st.divider()
    st.subheader("All signals and source evidence")
    st.caption(
        "Filter the signal set, then open the evidence rows for any signal. "
        "Confidence is the signal's evidence strength, not a probability."
    )
    render_all_signals(data)

    st.divider()
    render_error_log(data)
