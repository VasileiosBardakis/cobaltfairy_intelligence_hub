import pandas as pd
import plotly.express as px
import streamlit as st

from ..components import (
    render_competitor_snapshot,
    render_coverage_matrix,
    render_signal_card,
)
from ..data import (
    _pricing_view,
    _span,
    _top_per_type,
)
from ..theme import PLATFORM_COLORS, _style_fig


def render_fairymail(data):
    signals = data["signals"]

    st.subheader("Competitor snapshot")
    st.caption(
        "One card per competitor: captured pricing changes, top social themes "
        "and post coverage."
    )
    render_competitor_snapshot(data)

    st.subheader("Pricing comparison")
    changes = data["pricing_changes"].copy()
    for column in ["baseline_price", "price", "price_change", "price_change_pct"]:
        changes[column] = pd.to_numeric(changes[column], errors="coerce").round(2)
    with st.expander("Baseline vs current pricing", expanded=True):
        st.dataframe(
            _pricing_view(changes),
            hide_index=True,
            width="stretch",
            column_config={
                "Baseline": st.column_config.NumberColumn(format="$%.2f"),
                "Now": st.column_config.NumberColumn(format="$%.2f"),
                "Caveat": st.column_config.TextColumn(width="large"),
                "Source": st.column_config.LinkColumn(display_text="link"),
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
    social_signals = signals[signals["signal_type"] == "social_theme"]
    for row in _top_per_type(social_signals, 3).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Social coverage gaps")
    coverage = data["coverage"].copy()
    st.caption(
        f"Coverage window: "
        f"{_span(coverage['window_start'], coverage['window_end'])}. "
        "Gaps are reported as captured, not inferred."
    )
    render_coverage_matrix(data)
    with st.expander("Coverage details"):
        table = pd.DataFrame({
            "Brand": coverage["brand"],
            "Platform": coverage["platform"],
            "Coverage": coverage["status"].str.title(),
            "Posts": coverage["posts_captured"],
            "Window": coverage.apply(
                lambda row: f"{row['window_start']} to {row['window_end']}", axis=1
            ),
            "Captured": coverage["captured_at"],
            "Note": coverage["notes"],
        })
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                "Note": st.column_config.TextColumn(width="large"),
            },
        )
