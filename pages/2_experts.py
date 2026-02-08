"""Experts Page — Browse and discover 48 sales experts.

Flow B: search/filter → click card → profile dialog → "Chat with Expert" → Coach page.
Shows confidence badges, framework tags, and insight counts per expert.
"""
from __future__ import annotations

import streamlit as st

from components.expert_card import expert_card_html, expert_profile_html
from utils.data import (
    format_followers,
    get_avatar_base64,
    get_confidence_label,
    get_insight_counts_by_expert,
    get_persona,
    load_influencers,
    load_insights,
)
from utils.state import switch_persona


# ── Profile dialog ─────────────────────────────────────

@st.dialog("Expert Profile", width="large")
def show_profile(slug: str) -> None:
    """Show a full expert profile in a modal dialog."""
    influencers = load_influencers()
    details = None
    for inf in influencers:
        if inf["slug"] == slug:
            details = inf
            break

    if not details:
        st.error("Expert not found.")
        return

    # Render profile HTML
    profile_html = expert_profile_html(
        slug=slug,
        name=details["name"],
        specialty=details.get("specialty", ""),
        followers=details.get("followers"),
        focus_areas=details.get("focus_areas", []),
    )
    st.markdown(profile_html, unsafe_allow_html=True)

    # Persona-specific suggested questions
    persona = get_persona(slug)
    if persona and persona.get("suggested_questions"):
        st.markdown("---")
        st.markdown(
            '<p style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em">Suggested Questions</p>',
            unsafe_allow_html=True,
        )
        for i, q in enumerate(persona["suggested_questions"][:4]):
            if st.button(f"💬 {q}", key=f"prof_q_{slug}_{i}", use_container_width=True):
                switch_persona(slug)
                st.session_state.prefill_question = q
                st.switch_page("pages/1_coach.py")

    # "Chat with Expert" button
    st.markdown("---")
    if st.button(
        f"Chat with {details['name']}",
        key=f"chat_with_{slug}",
        type="primary",
        use_container_width=True,
    ):
        switch_persona(slug)
        st.switch_page("pages/1_coach.py")


# ── Expert grid (fragment for isolated reruns) ────────

@st.fragment
def _render_expert_grid() -> None:
    """Render the searchable, filterable expert grid."""
    influencers = load_influencers()
    insights = load_insights()
    insight_counts = get_insight_counts_by_expert(insights)

    # Search + filter row
    col_search, col_filter = st.columns([2, 1])

    with col_search:
        search = st.text_input(
            "Search experts",
            placeholder="Type a name or specialty...",
            key="experts_search",
            label_visibility="collapsed",
        )

    with col_filter:
        # Collect all unique focus areas
        all_focus_areas = set()
        for inf in influencers:
            for area in inf.get("focus_areas", []):
                all_focus_areas.add(area)

        focus_options = ["All focus areas"] + sorted(all_focus_areas)
        selected_focus = st.selectbox(
            "Focus area",
            options=focus_options,
            key="experts_focus_filter",
            label_visibility="collapsed",
        )

    # Filter influencers
    filtered = influencers

    if search:
        search_lower = search.lower()
        filtered = [
            inf for inf in filtered
            if search_lower in inf["name"].lower()
            or search_lower in inf.get("specialty", "").lower()
        ]

    if selected_focus and selected_focus != "All focus areas":
        filtered = [
            inf for inf in filtered
            if selected_focus in inf.get("focus_areas", [])
        ]

    # Sort by insight count (most content first)
    filtered.sort(key=lambda x: insight_counts.get(x["slug"], 0), reverse=True)

    # Results count
    st.markdown(
        f'<p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:8px">{len(filtered)} experts</p>',
        unsafe_allow_html=True,
    )

    # Grid layout: 3 columns
    if not filtered:
        st.info("No experts match your search.")
        return

    for row_start in range(0, len(filtered), 3):
        row = filtered[row_start:row_start + 3]
        cols = st.columns(3)

        for i, inf in enumerate(row):
            with cols[i]:
                slug = inf["slug"]
                count = insight_counts.get(slug, 0)

                # Render card HTML
                card = expert_card_html(
                    slug=slug,
                    name=inf["name"],
                    specialty=inf.get("specialty", ""),
                    followers=inf.get("followers"),
                    insight_count=count,
                )
                st.markdown(card, unsafe_allow_html=True)

                # Button to open profile dialog
                if st.button(
                    f"View {inf['name'].split()[0]}",
                    key=f"view_{slug}",
                    use_container_width=True,
                ):
                    show_profile(slug)


# ── Main ───────────────────────────────────────────────

def main() -> None:
    # Header
    st.markdown(
        """<div class="header-container">
            <div class="header-title"><h1>Sales Experts</h1></div>
            <p class="header-subtitle">Learn from 48 top sales leaders</p>
        </div>""",
        unsafe_allow_html=True,
    )

    _render_expert_grid()

    # Footer
    influencers = load_influencers()
    insights = load_insights()
    st.markdown(
        f'<div class="footer-text">{len(influencers)} experts · {len(insights)} total insights</div>',
        unsafe_allow_html=True,
    )


main()
