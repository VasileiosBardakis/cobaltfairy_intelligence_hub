import pandas as pd
import plotly.express as px
import streamlit as st

from ..components import render_coverage_cards, render_signal_card, show_signals
from ..data import (
    _pricing_view,
    _prioritized,
    _span,
    _top_per_type,
    _uncertain,
)
from ..theme import PLATFORM_COLORS, _style_fig


def render_fairymail(data):
    signals = data["signals"]
    evidence = data["evidence"]

    st.subheader("Competitive change feed")
    interpretation_label = (
        "Fixture interpretation"
        if data["mode"] == "synthetic"
        else "AI interpretation"
    )
    st.caption(
        "Pricing and social signals are ranked by review status and evidence strength. "
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

    st.subheader("Uncertainty handling")
    fairy_uncertain = _uncertain(
        signals[signals["signal_type"].isin(
            ["pricing_change", "social_theme", "cross_source"]
        )]
    )
    st.caption(
        "Isolated posts, low evidence strength and coverage gaps are kept "
        "separate from findings."
    )
    if fairy_uncertain.empty:
        st.success("No uncertain FairyMail signals.")
    else:
        for row in _prioritized(fairy_uncertain).itertuples(index=False):
            render_signal_card(row, data)
