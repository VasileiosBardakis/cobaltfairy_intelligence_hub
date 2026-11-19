import pandas as pd
import streamlit as st

from .data import (
    _evidence_count,
    _evidence_ids_text,
    _evidence_view,
    _period,
    _period_rows,
    _theme_label_map,
)
from .theme import (
    STATUS_RANK,
    STATUS_TONES,
    _claim_pill,
    _confidence_label,
    _esc,
    _pill,
    _signal_label,
    _status_label,
    _status_pill,
)


def render_sidebar(data):
    periods = "".join(
        f'<div class="side-period">'
        f'<div class="side-period-label">{_esc(label)}</div>'
        f'<div class="side-period-value">{_esc(value)}</div>'
        f"</div>"
        for label, value in _period_rows(data)
    )
    refreshed = pd.to_datetime(
        data["signals"]["created_at"], errors="coerce", utc=True
    ).max()
    refreshed_text = "n/a" if pd.isna(refreshed) else f"{refreshed:%Y-%m-%d %H:%M} UTC"

    with st.sidebar:
        st.markdown(
            f"""
            <div class="brand">
              <div class="brand-mark" aria-hidden="true">
                <span class="wing wing-left"></span>
                <span class="wing wing-right"></span>
              </div>
              <div>
                <div class="brand-eyebrow">Intelligence Hub</div>
                <div class="brand-title">Cobalt Fairy</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="side-section">
              <div class="side-label">Data periods</div>
              {periods}
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_legend()
        st.markdown(
            f"""
            <div class="side-note">
              Signals generated {_esc(refreshed_text)}.<br>
              Read-only prototype. AI output is pre-generated; no live AI calls.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_hero(data):
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">Cobalt Fairy · Market & Competitive Intelligence</div>
          <h1>Signals worth your attention.</h1>
          <p>
            An evidence-first view of Cobalt Fairy's portfolio and FairyMail's
            competitive landscape. See what changed, why it matters, and exactly
            which source supports it.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(data):
    signals = data["signals"]
    claims = data["claims"]
    reviewable = signals[signals["status"].isin(["candidate", "inferential"])]
    cross_count = int((signals["signal_type"] == "cross_source").sum())
    verified = int((claims["verification_status"] == "verified").sum())
    gaps = int(data["coverage"]["status"].ne("complete").sum())
    items = [
        (len(reviewable), "Signals to review", "open items", "blue"),
        (cross_count, "Cross-source patterns", "shared across sources", "lavender"),
        (
            f"{verified}/{len(claims)}",
            "Claims quote-matched",
            "automated exact-quote check",
            "mint",
        ),
        (gaps, "Coverage caveats", "source limits", "peach"),
    ]
    cards = "".join(
        f'<div class="metric-card {tone}">'
        f'<div class="metric-value">{_esc(value)}</div>'
        f'<div class="metric-label">{_esc(label)}</div>'
        f'<div class="metric-hint">{_esc(hint)}</div>'
        f"</div>"
        for value, label, hint, tone in items
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)
    st.caption(
        "Quote-matched is an automated exact-quote check, not human sign-off. "
        "Review every claim and its source in the Evidence tab."
    )


def render_competitor_snapshot(data):
    brands = ["Mailchimp", "Brevo", "MailerLite"]
    social = data["social"]
    changes = data["pricing_changes"]
    coverage = data["coverage"]
    label_map = _theme_label_map()

    labels = data["theme_labels"].copy()
    if not labels.empty:
        labels["confidence"] = pd.to_numeric(labels["confidence"], errors="coerce")
        labels = labels[labels["confidence"] >= 0.5]
        labels = labels.merge(
            social[["post_id", "brand"]], on="post_id", how="left"
        )

    cols = st.columns(len(brands))
    for col, brand in zip(cols, brands):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="card-kicker">Competitor</div>'
                    f'<div class="card-title">{_esc(brand)}</div>',
                    unsafe_allow_html=True,
                )

                brand_changes = changes[changes["platform"] == brand]
                changed = brand_changes[
                    brand_changes["change_type"].isin(["price_change", "new_plan"])
                    | brand_changes["plan_renamed"]
                ]
                renamed_plans = brand_changes.loc[
                    brand_changes["plan_renamed"], "baseline_plan"
                ].nunique()
                renames = int(renamed_plans)
                change_word = "change" if len(changed) == 1 else "changes"
                rename_word = "rename" if renames == 1 else "renames"
                st.markdown(
                    f"**Pricing:** {len(changed)} {change_word} · "
                    f"{renames} {rename_word}"
                )

                brand_labels = labels[labels["brand"] == brand] if not labels.empty else labels
                counts = (
                    brand_labels.groupby("theme_id")
                    .size()
                    .sort_values(ascending=False)
                    .head(2)
                )
                if counts.empty:
                    themes = "No labelled themes"
                else:
                    themes = ", ".join(
                        f"{label_map.get(theme, theme)} ({count})"
                        for theme, count in counts.items()
                    )
                st.markdown(f"**Top themes:** {themes}")

                brand_social = social[social["brand"] == brand]
                fb = int((brand_social["platform"] == "Facebook").sum())
                li = int((brand_social["platform"] == "LinkedIn").sum())
                st.markdown(f"**Posts:** FB {fb} · LI {li}")

                brand_cov = coverage[coverage["brand"] == brand]
                if brand_cov.empty:
                    status = "n/a"
                    tone = "gray"
                elif (brand_cov["status"] == "partial").any():
                    status = "partial"
                    tone = "amber"
                else:
                    status = "unavailable"
                    tone = "amber"
                st.markdown(
                    f'<div class="pill-row">{_pill("coverage " + status, tone)}</div>',
                    unsafe_allow_html=True,
                )

    st.caption(
        "Pricing counts include changes, new plans and renames. "
        "Top themes count theme labels; a post can carry more than one theme."
    )


def render_legend():
    blocks = [
        (
            "Data source",
            [
                ("Observed", "cobalt", "Raw source data"),
                ("Calculated", "violet", "Deterministic metrics"),
                ("AI-assisted", "green", "Pre-generated, checked text"),
            ],
        ),
        (
            "Signal status",
            [
                ("Needs review", "cobalt", "Validate before use"),
                ("Suggested link", "violet", "Related sources, not causal"),
                ("Not enough evidence", "amber", "Not a trend"),
            ],
        ),
        (
            "Quote checks",
            [
                ("Quote matched", "green", "Automated exact-quote check"),
                ("Needs review", "amber", "No exact quote, human review required"),
            ],
        ),
    ]
    legend_html = "".join(
        f'<div class="legend-block">'
        f'<div class="legend-heading">{_esc(heading)}</div>'
        + "".join(
            f'<div class="legend-item">'
            f"{_pill(label, tone)}"
            f'<span class="legend-desc">{_esc(description)}</span>'
            f"</div>"
            for label, tone, description in items
        )
        + "</div>"
        for heading, items in blocks
    )
    with st.expander("How to read this hub"):
        st.markdown(legend_html, unsafe_allow_html=True)



def render_coverage_matrix(data):
    coverage = data["coverage"].copy()
    coverage["posts_captured"] = pd.to_numeric(
        coverage["posts_captured"], errors="coerce"
    ).fillna(0).astype(int)

    brands = ["Mailchimp", "Brevo", "MailerLite"]
    brands = [brand for brand in brands if brand in set(coverage["brand"])]
    platforms = ["Facebook", "LinkedIn", "Instagram"]

    rows = []
    for brand in brands:
        row = {"Brand": brand}
        for platform in platforms:
            match = coverage[
                (coverage["brand"] == brand) & (coverage["platform"] == platform)
            ]
            if match.empty:
                row[platform] = "n/a"
            else:
                posts = int(match["posts_captured"].iloc[0])
                status = str(match["status"].iloc[0]).title()
                row[platform] = f"{posts} · {status}"
        rows.append(row)

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Brand": st.column_config.TextColumn(width="medium"),
            "Facebook": st.column_config.TextColumn(
                help="Captured posts · coverage state"
            ),
            "LinkedIn": st.column_config.TextColumn(
                help="Captured posts · coverage state"
            ),
            "Instagram": st.column_config.TextColumn(
                help="Captured posts · coverage state"
            ),
        },
    )
    st.caption("Counts are captured posts; the second value is the coverage state.")


def _signal_view(signals):
    view = signals.copy()
    view["period"] = [
        _period(start, end)
        for start, end in zip(view["period_start"], view["period_end"])
    ]
    return pd.DataFrame({
        "Signal": view["title"],
        "Type": view["signal_type"].map(_signal_label),
        "Period": view["period"],
        "Status": view["status"].map(_status_label),
        "Evidence strength": view["confidence"].map(_confidence_label),
        "Coverage note": view["coverage_note"],
    })


def render_all_signals(data):
    signals = data["signals"].copy()
    evidence = data["evidence"]
    if signals.empty:
        st.info("No signals available.")
        return

    label_map = _theme_label_map()

    col1, col2, col3 = st.columns(3)
    with col1:
        types = st.multiselect(
            "Type", sorted(signals["signal_type"].unique()),
            format_func=_signal_label,
            key="all_signals_type",
        )
    with col2:
        statuses = st.multiselect(
            "Status", sorted(signals["status"].unique()),
            format_func=_status_label,
            key="all_signals_status",
        )
    with col3:
        entities = st.multiselect(
            "Entity", sorted(signals["entity"].unique()),
            format_func=lambda value: label_map.get(value, value),
            key="all_signals_entity",
        )
    search = st.text_input("Search signals", key="all_signals_search")

    view = signals
    if types:
        view = view[view["signal_type"].isin(types)]
    if statuses:
        view = view[view["status"].isin(statuses)]
    if entities:
        view = view[view["entity"].isin(entities)]
    if search.strip():
        needle = search.strip().lower()
        mask = (
            view["title"].str.lower().str.contains(needle, na=False)
            | view["summary"].str.lower().str.contains(needle, na=False)
            | view["coverage_note"].str.lower().str.contains(needle, na=False)
        )
        view = view[mask]

    if view.empty:
        st.info("No signals match these filters.")
        return

    counts = evidence.groupby("signal_id").size()
    view = view.copy()
    view["evidence_count"] = view["signal_id"].map(counts).fillna(0).astype(int)
    view["_rank"] = view["status"].map(STATUS_RANK).fillna(len(STATUS_RANK))
    view = view.sort_values(["_rank", "confidence"], ascending=[True, False])

    table = pd.DataFrame({
        "Signal": view["title"],
        "Type": view["signal_type"].map(_signal_label),
        "Entity": view["entity"].map(lambda value: label_map.get(value, value)),
        "Period": [
            _period(start, end)
            for start, end in zip(view["period_start"], view["period_end"])
        ],
        "Status": view["status"].map(_status_label),
        "Evidence strength": view["confidence"].map(_confidence_label),
        "Evidence rows": view["evidence_count"],
        "Coverage note": view["coverage_note"],
    })
    st.caption(
        f"{len(view)} of {len(signals)} signals. "
        "Evidence rows are the source rows behind each signal."
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Evidence strength": st.column_config.TextColumn(
                help="High, medium or low based on the signal's confidence."
            ),
            "Evidence rows": st.column_config.NumberColumn(width="small"),
            "Coverage note": st.column_config.TextColumn(width="large"),
        },
    )

    options = {
        f"{row.title} · {_signal_label(row.signal_type)}": row.signal_id
        for row in view.itertuples(index=False)
    }
    with st.expander("Evidence for selected signal"):
        selected = st.selectbox(
            "Signal", list(options), key="all_signals_evidence"
        )
        rows = evidence[evidence["signal_id"] == options[selected]]
        if rows.empty:
            st.info("No captured evidence for this signal.")
        else:
            st.dataframe(
                _evidence_view(rows),
                hide_index=True,
                width="stretch",
                column_config={
                    "Evidence ID": st.column_config.TextColumn(width="medium"),
                    "Evidence": st.column_config.TextColumn(width="large"),
                    "Source URL": st.column_config.LinkColumn(display_text="link"),
                },
            )


def render_claim_rows(claims):
    if claims.empty:
        st.caption("No verified or inferential claims.")
        return

    rows = []
    for claim in claims.itertuples(index=False):
        quote_html = ""
        if isinstance(claim.quote, str) and claim.quote.strip():
            quote_html = f'<div class="quote">“{_esc(claim.quote)}”</div>'
        count = _evidence_count(claim.evidence_ids)
        ids_text = _evidence_ids_text(claim.evidence_ids)
        meta_html = ""
        if count:
            label = "source" if count == 1 else "sources"
            meta = f"{count} cited {label}"
            if ids_text:
                meta += f": {ids_text}"
            meta_html = f'<div class="claim-meta">{_esc(meta)}</div>'
        rows.append(
            f'<div class="claim-row">'
            f'{_claim_pill(claim.verification_status)}'
            f"<div>"
            f'<div class="claim-text">{_esc(claim.claim_text)}</div>'
            f"{quote_html}{meta_html}"
            f"</div></div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def render_signal_card(signal, data):
    tone = STATUS_TONES.get(signal.status, "gray")
    with st.container(border=True):
        st.markdown(
            f'<div class="accent accent-{tone}"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="card-kicker">{_esc(_signal_label(signal.signal_type))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="card-title">{_esc(signal.title)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="pill-row">'
            f"{_status_pill(signal.status)}"
            f'{_pill("evidence strength " + _confidence_label(signal.confidence).lower(), "gray")}'
            f'{_pill(_period(signal.period_start, signal.period_end), "gray")}'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write(signal.summary)
        st.markdown(
            f'<div class="card-note"><strong>Coverage / caveat</strong><br>'
            f"{_esc(signal.coverage_note)}</div>",
            unsafe_allow_html=True,
        )

        evidence = data["evidence"]
        briefs = data["briefs"]
        evidence_rows = evidence[evidence["signal_id"] == signal.signal_id]
        brief = briefs[briefs["signal_id"] == signal.signal_id]
        if evidence_rows.empty and brief.empty:
            st.caption("No captured evidence or AI output.")
            return

        with st.expander("Source evidence and AI output"):
            st.markdown(
                '<div class="card-kicker">Source evidence</div>',
                unsafe_allow_html=True,
            )
            if evidence_rows.empty:
                st.caption("No captured evidence.")
            else:
                st.dataframe(
                    _evidence_view(evidence_rows),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Evidence ID": st.column_config.TextColumn(width="medium"),
                        "Evidence": st.column_config.TextColumn(width="large"),
                        "Source URL": st.column_config.LinkColumn(display_text="link"),
                    },
                )

            st.markdown(
                f'<div class="pill-row" style="margin-top:14px;">'
                f'{_pill("AI interpretation", "violet")}'
                f'{_pill("pre-generated", "gray")}</div>',
                unsafe_allow_html=True,
            )
            if brief.empty:
                st.caption("No AI brief for this signal.")
                return

            item = brief.iloc[0]
            st.write(item["positioning"])
            checker = (
                "Automatically checked"
                if item["checker_status"] == "auto_checked"
                else item["checker_status"]
            )
            st.caption(
                f"Generated {item['created_at']} · {item['model']} · {checker}"
            )

            claims = data["claims"]
            claim_rows = claims[
                (claims["brief_id"] == item["brief_id"])
                & (claims["verification_status"] != "unsupported")
            ]
            render_claim_rows(claim_rows)


def render_briefs(data):
    briefs = data["briefs"].merge(
        data["signals"][["signal_id", "title", "signal_type", "status"]],
        on="signal_id",
        how="left",
    )
    if briefs.empty:
        st.info("No AI briefs available.")
        return

    options = {
        f"{row.title} · {_signal_label(row.signal_type)}": row.brief_id
        for row in briefs.itertuples(index=False)
    }
    selected = st.selectbox("AI brief", list(options), key="brief_select")
    brief = briefs[briefs["brief_id"] == options[selected]].iloc[0]

    st.markdown(
        f'<div class="pill-row">'
        f'{_pill("AI interpretation", "violet")}'
        f'{_pill("pre-generated", "gray")}'
        f'{_pill(_signal_label(brief["signal_type"]), "gray")}'
        f'{_status_pill(brief["status"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="card-title">{_esc(brief["title"])}</div>',
        unsafe_allow_html=True,
    )
    st.write(brief["positioning"])
    checker = (
        "Automatically checked"
        if brief["checker_status"] == "auto_checked"
        else brief["checker_status"]
    )
    st.caption(
        f"Generated {brief['created_at']} · {brief['model']} · {checker} · "
        f"{_status_label(brief['status'])}"
    )

    claims = data["claims"]
    visible = claims[
        (claims["brief_id"] == brief["brief_id"])
        & (claims["verification_status"] != "unsupported")
    ]
    render_claim_rows(visible)


def render_inference_queue(data):
    claims = data["claims"]
    inferential = claims[claims["verification_status"] == "inferential"]
    briefs = data["briefs"]
    review_briefs = briefs[briefs["checker_status"] == "needs_review"].merge(
        data["signals"][["signal_id", "title"]], on="signal_id", how="left"
    )
    st.caption(
        "These AI claims make a statement without an exact supporting quote, "
        "and these briefs failed the positioning check. Both are kept for "
        "review and are not treated as verified."
    )
    if inferential.empty:
        st.success("No claims need review.")
    else:
        rows = inferential.merge(
            data["signals"][["signal_id", "title"]], on="signal_id", how="left"
        )
        table = pd.DataFrame({
            "Signal": rows["title"],
            "Claim": rows["claim_text"],
            "Why it needs review": rows["checker_note"].replace(
                "", "No exact supporting quote"
            ),
        })
        st.dataframe(table, hide_index=True, width="stretch")

    if not review_briefs.empty:
        st.markdown("**Briefs needing review**")
        table = pd.DataFrame({
            "Signal": review_briefs["title"],
            "Why it needs review": review_briefs["checker_note"],
            "Positioning": review_briefs["positioning"],
        })
        st.dataframe(table, hide_index=True, width="stretch")


def render_claims_audit(data):
    claims = data["claims"].copy()
    if claims.empty:
        st.info("No claims available.")
        return

    claims = claims.merge(
        data["signals"][["signal_id", "title"]], on="signal_id", how="left"
    )
    claims = claims[claims["verification_status"] != "unsupported"]
    if claims.empty:
        st.info("No verified or inferential claims available.")
        return

    rank = {"inferential": 0, "verified": 1}
    claims["_rank"] = claims["verification_status"].map(rank).fillna(2)
    claims = claims.sort_values(["_rank", "claim_id"])
    status_labels = {
        "verified": "Quote matched",
        "inferential": "Needs review",
    }

    st.caption(
        f"All {len(claims)} claims across {claims['brief_id'].nunique()} briefs. "
        "'Quote matched' is an automated exact-quote check, not human sign-off. "
        "Unsupported claims stay in the error log below."
    )
    choice = st.selectbox(
        "Status",
        ["All claims", "Needs review", "Quote matched"],
        key="claims_audit_status",
    )
    if choice == "Needs review":
        claims = claims[claims["verification_status"] == "inferential"]
    elif choice == "Quote matched":
        claims = claims[claims["verification_status"] == "verified"]

    table = pd.DataFrame({
        "Signal": claims["title"],
        "Claim": claims["claim_text"],
        "Status": claims["verification_status"].map(status_labels),
        "Evidence IDs": claims["evidence_ids"].map(_evidence_ids_text),
        "Quote": claims["quote"].fillna(""),
        "Checker note": claims["checker_note"].fillna(""),
    })
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Claim": st.column_config.TextColumn(width="large"),
            "Evidence IDs": st.column_config.TextColumn(width="medium"),
            "Quote": st.column_config.TextColumn(width="large"),
        },
    )


def render_theme_audit(data):
    labels = data["theme_labels"].copy()
    if labels.empty:
        st.info("No theme labels available.")
        return
    social = data["social"][["post_id", "brand", "platform", "posted_at"]]
    labels = labels.merge(social, on="post_id", how="left")
    label_map = _theme_label_map()
    labels["confidence"] = pd.to_numeric(labels["confidence"], errors="coerce")
    model = ", ".join(sorted({
        str(value) for value in labels["model"].dropna().unique()
    }))
    st.caption(
        f"{len(labels)} labels across {labels['post_id'].nunique()} posts. "
        f"Model: {model or 'n/a'}. Every label stores an exact quote from the post."
    )
    table = pd.DataFrame({
        "Brand": labels["brand"],
        "Platform": labels["platform"],
        "Date": labels["posted_at"],
        "Theme": labels["theme_id"].map(
            lambda value: label_map.get(
                value, str(value).replace("_", " ").title()
            )
        ),
        "Evidence strength": labels["confidence"].map(_confidence_label),
        "Quote": labels["evidence_quote"],
    })
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Evidence strength": st.column_config.TextColumn(
                help="High, medium or low based on the label confidence."
            ),
            "Quote": st.column_config.TextColumn(width="large"),
        },
    )


def render_error_log(data):
    claims = data["claims"]
    unsupported = claims[claims["verification_status"] == "unsupported"]
    issues = data["issues"]

    st.subheader("Error log")
    st.caption(
        "Unsupported claims and mapping issues are shown only here and are "
        "excluded from the verified output."
    )

    with st.expander(
        f"Unsupported claims ({len(unsupported)})", expanded=not unsupported.empty
    ):
        if unsupported.empty:
            st.success("No unsupported claims.")
        else:
            rows = unsupported.merge(
                data["signals"][["signal_id", "title"]],
                on="signal_id",
                how="left",
            )
            table = pd.DataFrame({
                "Signal": rows["title"],
                "Claim": rows["claim_text"],
                "Why rejected": rows["checker_note"],
            })
            st.dataframe(table, hide_index=True, width="stretch")

    with st.expander(f"Mapping issues ({len(issues)})", expanded=not issues.empty):
        if issues.empty:
            st.success("No mapping issues.")
        else:
            parts = issues["mapping_id"].str.split("|", expand=True)
            table = pd.DataFrame({
                "CF subgenre": parts[2],
                "Market category": parts[3],
                "Month": issues["month"],
                "Issue": issues["issue"],
            })
            st.dataframe(table, hide_index=True, width="stretch")
