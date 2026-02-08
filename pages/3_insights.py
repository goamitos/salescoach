"""Insights Page — Browse insights by stage, methodology, and expert.

Flow C: stage tabs → filter → browse cards → "Ask about this" → Coach page.
Also includes the Methodology Explorer for browsing 10 sales methodologies.
"""
from __future__ import annotations

import streamlit as st

from components.insight_card import insight_card_html
from components.methodology_badge import (
    methodology_card_html,
    methodology_component_detail_html,
)
from components.stage_pills import (
    stage_group_options,
    stage_option_to_value,
    value_to_stage_option,
)
from utils.data import (
    STAGE_GROUPS,
    filter_insights,
    get_influencer_name,
    get_stage_counts,
    load_influencers,
    load_insights,
    load_methodologies,
    search_insights_fts,
)
from utils.state import set_prefill_and_navigate, sync_query_params

PAGE_SIZE = 20


# ── Methodology component dialog ──────────────────────

@st.dialog("Methodology Component", width="large")
def show_component(component: dict, methodology_name: str) -> None:
    """Show a methodology component detail in a modal."""
    html = methodology_component_detail_html(component, methodology_name)
    st.markdown(html, unsafe_allow_html=True)

    # Show related insights if tagged
    component_id = component.get("id", "")
    insights = load_insights()
    related = [
        i for i in insights
        if any(
            t.get("component_id") == component_id
            for t in (i.get("methodology_tags") or [])
        )
    ][:5]

    if related:
        st.markdown("---")
        st.markdown(
            f'<p style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em">{len(related)} Related Insights</p>',
            unsafe_allow_html=True,
        )
        for insight in related:
            card = insight_card_html(insight)
            st.markdown(card, unsafe_allow_html=True)


# ── Methodology explorer section ──────────────────────

@st.fragment
def _render_methodology_explorer() -> None:
    """Render the methodology explorer with cards and component drill-down."""
    methodologies = load_methodologies()
    if not methodologies:
        st.info("Methodology data not yet available. Run the database-scaling pipeline to populate.")
        return

    # Organize by category
    categories = {}
    for m in methodologies:
        cat = m.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(m)

    # Tabs by category
    cat_names = list(categories.keys())
    if not cat_names:
        return

    tab_labels = [cat.title() for cat in cat_names]
    tabs = st.tabs(tab_labels)

    for tab, cat_name in zip(tabs, cat_names):
        with tab:
            for m in categories[cat_name]:
                card = methodology_card_html(m)
                st.markdown(card, unsafe_allow_html=True)

                # Component buttons
                components = m.get("components", [])
                if components:
                    comp_cols = st.columns(min(len(components), 4))
                    for j, comp in enumerate(components):
                        col_idx = j % min(len(components), 4)
                        with comp_cols[col_idx]:
                            label = comp.get("abbreviation") or comp.get("name", "")
                            if st.button(
                                label,
                                key=f"comp_{m['id']}_{comp.get('id', j)}",
                                use_container_width=True,
                            ):
                                show_component(comp, m["name"])

                st.markdown("---")


# ── Insights browse section ────────────────────────────

@st.fragment
def _render_insights_browser() -> None:
    """Render the filterable, paginated insights browser."""
    insights = load_insights()
    influencers = load_influencers()

    # Filters row
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search_query = st.text_input(
            "Search insights",
            placeholder="Search by keyword, topic, or quote...",
            key="insights_search",
            label_visibility="collapsed",
        )

    with col2:
        # Expert filter
        expert_names = ["All experts"] + sorted(
            set(i.get("influencer_name", "") for i in insights if i.get("influencer_name"))
        )
        selected_expert_name = st.selectbox(
            "Expert",
            options=expert_names,
            key="insights_expert_filter",
            label_visibility="collapsed",
        )

    with col3:
        # Methodology filter
        methodologies = load_methodologies()
        method_options = ["All methodologies"]
        method_map = {}
        for m in methodologies:
            method_options.append(m["name"])
            method_map[m["name"]] = m["id"]

        selected_method_name = st.selectbox(
            "Methodology",
            options=method_options,
            key="insights_method_filter",
            label_visibility="collapsed",
        )

    # Stage tabs
    counts = get_stage_counts(insights)
    tab_labels = ["All"] + list(STAGE_GROUPS.keys()) + ["Mindset"]
    tab_counts = [
        counts.get("All", 0),
        *[counts.get(g, 0) for g in STAGE_GROUPS],
        counts.get("Mindset", 0),
    ]
    tab_display = [f"{label} ({count})" for label, count in zip(tab_labels, tab_counts)]

    tabs = st.tabs(tab_display)

    for tab, tab_label in zip(tabs, tab_labels):
        with tab:
            # Determine stage group
            if tab_label == "All":
                stage_group = "All"
            elif tab_label == "Mindset":
                stage_group = "General Sales Mindset"
            else:
                stage_group = tab_label

            # Apply filters
            # Expert slug from name
            expert_slug = None
            if selected_expert_name != "All experts":
                for inf in influencers:
                    if inf["name"] == selected_expert_name:
                        expert_slug = inf["slug"]
                        break

            methodology_id = method_map.get(selected_method_name)

            if search_query:
                filtered = search_insights_fts(search_query, limit=100)
                # Apply additional filters on FTS results
                filtered = filter_insights(
                    filtered,
                    expert_slug=expert_slug,
                    stage_group=stage_group,
                    methodology_id=methodology_id,
                )
            else:
                filtered = filter_insights(
                    insights,
                    expert_slug=expert_slug,
                    stage_group=stage_group,
                    methodology_id=methodology_id,
                )

            # Sort
            sort_key = f"sort_{tab_label}"
            sort_option = st.selectbox(
                "Sort by",
                options=["Relevance", "Expert", "Newest"],
                key=sort_key,
                label_visibility="collapsed",
            )

            if sort_option == "Expert":
                filtered.sort(key=lambda x: x.get("influencer_name", ""))
            elif sort_option == "Newest":
                filtered.sort(key=lambda x: x.get("date_collected", ""), reverse=True)
            # Relevance is default order (relevance_score DESC from DB)

            # Results count
            st.markdown(
                f'<p style="font-size:0.8rem;color:var(--text-muted)">{len(filtered)} insights</p>',
                unsafe_allow_html=True,
            )

            # Pagination
            page_key = f"page_{tab_label}"
            if page_key not in st.session_state:
                st.session_state[page_key] = 1

            current_page = st.session_state[page_key]
            visible = filtered[:current_page * PAGE_SIZE]

            # Render insight cards
            for i, insight in enumerate(visible):
                card = insight_card_html(insight)
                st.markdown(card, unsafe_allow_html=True)

                # "Ask about this" button
                key_insight = insight.get("key_insight", "")
                if key_insight:
                    short = key_insight[:60] + "..." if len(key_insight) > 60 else key_insight
                    if st.button(
                        f"Ask about this",
                        key=f"ask_{tab_label}_{i}",
                    ):
                        question = f"Tell me more about: {key_insight[:100]}"
                        # Set expert context if the insight has one
                        slug = insight.get("influencer_slug")
                        if slug:
                            st.session_state.selected_persona = slug
                        set_prefill_and_navigate(question)
                        st.switch_page("pages/1_coach.py")

            # "Load more" button
            if len(filtered) > current_page * PAGE_SIZE:
                remaining = len(filtered) - current_page * PAGE_SIZE
                if st.button(
                    f"Load more ({remaining} remaining)",
                    key=f"load_more_{tab_label}",
                    use_container_width=True,
                ):
                    st.session_state[page_key] = current_page + 1
                    st.rerun(scope="fragment")


# ── Main ───────────────────────────────────────────────

def main() -> None:
    sync_query_params()

    st.markdown(
        """<div class="header-container">
            <div class="header-title"><h1>Insights</h1></div>
            <p class="header-subtitle">Browse coaching wisdom by stage, methodology, and expert</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # Two sections: Methodology Explorer (collapsible) + Insights Browser
    view_tabs = st.tabs(["Browse Insights", "Methodology Explorer"])

    with view_tabs[0]:
        _render_insights_browser()

    with view_tabs[1]:
        _render_methodology_explorer()

    # Footer
    insights = load_insights()
    influencer_count = len(load_influencers())
    methodology_count = len(load_methodologies())

    footer_parts = [f"{len(insights)} insights", f"{influencer_count} experts"]
    if methodology_count > 0:
        footer_parts.append(f"{methodology_count} methodologies")

    st.markdown(
        f'<div class="footer-text">{" · ".join(footer_parts)}</div>',
        unsafe_allow_html=True,
    )


main()
