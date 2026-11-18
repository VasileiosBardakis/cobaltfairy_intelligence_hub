import pandas as pd
import plotly.express as px
import streamlit as st

from ..components import render_signal_card
from ..data import (
    _cf_findings,
    _finding_sentence,
    _month_range,
    _prioritized,
    _uncertain,
)
from ..theme import CF_COLORS, _confidence_label, _style_fig


def render_cobalt_fairy(data):
    signals = data["signals"]

    st.subheader("Market vs portfolio")
    st.caption(
        f"Commercial and market months: {_month_range(data['cf']['month'])}. "
        "Category mappings are manually reviewed; confidence is shown per mapping."
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
            "Thin or low-evidence mappings are handled in Uncertainty."
        )

        primary = comparable[comparable["relationship"] == "primary"]
        headline = primary if not primary.empty else comparable
        strongest = headline.sort_values("relative_units_gap").iloc[-1]
        weakest = headline.sort_values("relative_units_gap").iloc[0]
        st.markdown(f"- **Strongest relative performance:** {_finding_sentence(strongest)}")
        st.markdown(f"- **Weakest relative performance:** {_finding_sentence(weakest)}")

    if not comparable.empty:
        table = pd.DataFrame({
            "CF subgenre": comparable["source_label"],
            "Market category": comparable["target_path"],
            "Mapping": comparable["relationship"].str.title(),
            "Titles compared": comparable["same_title_n"].astype("Int64"),
            "CF units/day change": comparable["same_title_units_change_pct"].map(
                lambda value: f"{value:+.1f}%"
            ),
            "Market growth": comparable["market_growth_pct"].map(
                lambda value: f"{value:+.1f}%"
            ),
            "Relative gap": comparable["relative_units_gap"].map(
                lambda value: f"{value:+.1f} pp"
            ),
            "Price gap": comparable["price_gap_pct"].map(
                lambda value: f"{value:+.1f}%"
            ),
            "Mapping confidence": comparable["confidence"].map(_confidence_label),
        })
        st.dataframe(table, hide_index=True, width="stretch")

    st.subheader("CF signals")
    cf_signals = signals[signals["signal_type"] == "cf_market"]
    for row in _prioritized(cf_signals).itertuples(index=False):
        render_signal_card(row, data)

    st.subheader("Mapping confidence and ambiguity")
    mappings = data["mappings"].copy()
    mappings["confidence"] = pd.to_numeric(mappings["confidence"], errors="coerce")
    mappings = mappings.sort_values("confidence")
    table = pd.DataFrame({
        "CF subgenre": mappings["source_label"],
        "Market category": mappings["target_path"],
        "Mapping": mappings["relationship"].str.title(),
        "Why this mapping": mappings["rationale"],
        "Mapping confidence": mappings["confidence"].map(_confidence_label),
    })
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Why this mapping": st.column_config.TextColumn(width="large"),
        },
    )

    st.subheader("Uncertainty handling")
    cf_uncertain = _uncertain(cf_signals)
    st.caption(
        "Ambiguous mappings or thin comparisons are flagged rather than silently "
        "treated as equivalent categories."
    )
    if cf_uncertain.empty:
        st.success("No uncertain CF signals.")
    else:
        for row in _prioritized(cf_uncertain).itertuples(index=False):
            render_signal_card(row, data)
