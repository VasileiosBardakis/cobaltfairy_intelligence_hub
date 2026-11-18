import pandas as pd
import plotly.express as px
import streamlit as st

from ..components import render_signal_card
from ..data import _cf_findings, _prioritized
from ..theme import _confidence_label, _style_fig

MATCH_LABELS = {
    "primary": "Direct match",
    "secondary": "Broader match",
}


def _match_label(value):
    return MATCH_LABELS.get(str(value), str(value).title())


def _month_label(values):
    months = pd.Series(
        pd.to_datetime(
            pd.Series(values).dropna().astype(str).unique(),
            errors="coerce",
        )
    ).dropna().sort_values()
    if months.empty:
        return "the period"
    start, end = months.iloc[0], months.iloc[-1]
    if start == end:
        return f"{start:%b %Y}"
    if start.year == end.year:
        return f"{start:%b}–{end:%b %Y}"
    return f"{start:%b %Y}–{end:%b %Y}"


def _row_label(row):
    leaf = str(row["target_path"]).split("-")[-1]
    direct = str(row["source_label"]).split(" / ")[0]
    if leaf == direct:
        return row["source_label"]
    return f"{row['source_label']} titles in {leaf}"


def _gap_label(value):
    if value >= 0:
        return f"{value:.1f} points ahead"
    return f"{abs(value):.1f} points behind"


def _change_text(value):
    if value >= 0:
        return f"up {value:.1f}%"
    return f"down {abs(value):.1f}%"


def _takeaway(row, best):
    market_word = "grew" if row["market_growth_pct"] >= 0 else "fell"
    position = "ahead of" if best else "behind"
    return (
        f"**{_row_label(row)}**: {abs(row['relative_units_gap']):.1f} points "
        f"{position} the market — sales "
        f"{_change_text(row['same_title_units_change_pct'])} while the market "
        f"{market_word} {abs(row['market_growth_pct']):.1f}%."
    )


def _growth_comparison_figure(comparable):
    chart = comparable.copy()
    chart["row"] = [
        f"{_row_label(row)}<br>{_gap_label(row['relative_units_gap'])}"
        for _, row in chart.iterrows()
    ]
    order = chart.sort_values("relative_units_gap")["row"].tolist()
    long = chart.melt(
        id_vars=["row", "target_path", "titles", "price_gap_pct", "confidence"],
        value_vars=["market_growth_pct", "same_title_units_change_pct"],
        var_name="series",
        value_name="growth",
    )
    long["series"] = long["series"].map({
        "market_growth_pct": "Market",
        "same_title_units_change_pct": "Cobalt Fairy",
    })
    long["value_label"] = long["growth"].map(lambda value: f"{value:+.0f}%")

    fig = px.bar(
        long,
        x="growth",
        y="row",
        color="series",
        barmode="group",
        orientation="h",
        color_discrete_map={"Market": "#9AA1B2", "Cobalt Fairy": "#2F63F7"},
        text="value_label",
        hover_data={
            "target_path": True,
            "titles": True,
            "price_gap_pct": ":.1f",
            "confidence": ":.2f",
            "value_label": False,
            "row": False,
        },
        labels={
            "growth": "Sales growth (%)",
            "row": "",
            "series": "",
            "target_path": "Matched market category",
            "titles": "Titles in both months",
            "price_gap_pct": "Price vs market (%)",
            "confidence": "Match confidence",
        },
        title="Cobalt Fairy vs market: sales growth by category",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)

    x_low = long["growth"].min()
    x_high = long["growth"].max()
    padding = max(2.0, (x_high - x_low) * 0.22)
    fig.update_xaxes(range=[x_low - padding, x_high + padding], ticksuffix="%")
    fig.update_yaxes(categoryorder="array", categoryarray=order)
    fig.add_vline(x=0, line_dash="dash", line_color="#BCB3A3", line_width=1)
    fig.update_layout(bargap=0.28)
    return _style_fig(fig, 430)


def render_cobalt_fairy(data):
    signals = data["signals"]

    st.subheader("Cobalt Fairy vs market")
    st.caption(
        f"How Cobalt Fairy sales compare with the matched market, "
        f"{_month_label(data['cf']['month'])}. Like-for-like titles only."
    )

    findings = _cf_findings(data["summary"], data["same_title"])
    comparable = findings[
        (findings["same_title_n"] >= 5)
        & findings["market_growth_pct"].notna()
        & findings["same_title_units_change_pct"].notna()
    ] if not findings.empty else findings
    if comparable.empty:
        st.info("No comparable category data available.")
    else:
        ranked = comparable.sort_values("relative_units_gap")
        st.markdown(_takeaway(ranked.iloc[-1], best=True))
        st.markdown(_takeaway(ranked.iloc[0], best=False))
        st.plotly_chart(
            _growth_comparison_figure(comparable),
            width="stretch",
            config={"displayModeBar": False},
        )
        st.caption(
            "Bars show sales growth for titles available in both months. "
            "Rows are sorted by the gap; the market is the matched category. "
            "One point is one percentage point of growth."
        )

    with st.expander("Data and category matching"):
        if not comparable.empty:
            detail = comparable.sort_values("relative_units_gap", ascending=False)
            table = pd.DataFrame({
                "Cobalt Fairy category": detail["source_label"],
                "Matched market category": detail["target_path"],
                "Match": detail["relationship"].map(_match_label),
                "Titles in both months": detail["same_title_n"].astype("Int64"),
                "Cobalt Fairy sales change": detail[
                    "same_title_units_change_pct"
                ].map(lambda value: f"{value:+.1f}%"),
                "Market sales change": detail["market_growth_pct"].map(
                    lambda value: f"{value:+.1f}%"
                ),
                "Ahead / behind": detail["relative_units_gap"].map(_gap_label),
                "Price vs market": detail["price_gap_pct"].map(
                    lambda value: f"{value:+.1f}%"
                ),
                "Match confidence": detail["confidence"].map(_confidence_label),
            })
            st.dataframe(table, hide_index=True, width="stretch")

        st.markdown("**Category matching**")
        st.caption(
            "Matches are manually reviewed. Lower confidence means the category "
            "match is less certain, not that the sales comparison is wrong."
        )
        mappings = data["mappings"].copy()
        mappings["confidence"] = pd.to_numeric(
            mappings["confidence"], errors="coerce"
        )
        mappings = mappings.sort_values("confidence")
        table = pd.DataFrame({
            "Cobalt Fairy category": mappings["source_label"],
            "Matched market category": mappings["target_path"],
            "Match": mappings["relationship"].map(_match_label),
            "Why this match": mappings["rationale"],
            "Match confidence": mappings["confidence"].map(_confidence_label),
        })
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                "Why this match": st.column_config.TextColumn(width="large"),
            },
        )

    with st.expander("More Cobalt Fairy signals and evidence"):
        cf_signals = signals[signals["signal_type"] == "cf_market"]
        if cf_signals.empty:
            st.info("No category signals.")
        else:
            for row in _prioritized(cf_signals).itertuples(index=False):
                render_signal_card(row, data)
