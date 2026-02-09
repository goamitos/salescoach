"""Coach Page — AI-powered chat with expert coaching.

Primary flow: user describes a deal situation, gets synthesized advice
from 48 experts with inline source cards. Supports persona mode
("Coaching as Chris Voss") and stage/methodology filters.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from components.chat_message import render_chat_messages
from components.insight_card import source_card_html
from components.stage_pills import (
    stage_group_options,
    stage_option_to_value,
    value_to_stage_option,
)
from utils.ai import (
    generate_conversation_title,
    get_anthropic_key,
    get_coaching_advice,
    synthesize_stage_insight,
)
from utils.data import (
    filter_insights,
    get_avatar_base64,
    get_confidence_label,
    get_influencer_details,
    get_influencer_name,
    get_stage_counts,
    load_influencers,
    load_insights,
    load_methodologies,
    load_personas,
    get_persona,
)
from utils.search import build_context, find_relevant_insights
from utils.state import reset_conversation, switch_persona, sync_query_params, update_query_params


# ── Header ─────────────────────────────────────────────

def _render_header() -> None:
    """Render the coach page header with title."""
    st.markdown(
        """<div class="header-container">
            <div class="header-title"><h1>Sales Coach AI</h1></div>
            <p class="header-subtitle">Expert coaching from 48 sales leaders</p>
        </div>""",
        unsafe_allow_html=True,
    )


# ── Expert Selection (popover + featured row) ──────────

def _render_expert_selector() -> None:
    """Render the expert selector: featured avatars + searchable popover."""
    influencers = load_influencers()
    selected = st.session_state.get("selected_persona")

    # Featured experts row (top 6 by followers + collective wisdom)
    sorted_by_followers = sorted(
        influencers, key=lambda x: x.get("followers") or 0, reverse=True
    )
    featured = sorted_by_followers[:6]

    # Build featured row HTML
    featured_html_parts = []

    # Collective wisdom first
    cw_b64 = get_avatar_base64("collective-wisdom")
    cw_selected = "selected" if selected is None else ""
    featured_html_parts.append(
        f'<div class="featured-expert {cw_selected}">'
        f'<img src="data:image/png;base64,{cw_b64}">'
        f'<span class="name">All</span></div>'
    )

    for inf in featured:
        b64 = get_avatar_base64(inf["slug"])
        is_sel = "selected" if selected == inf["slug"] else ""
        first_name = inf["name"].split()[0]
        featured_html_parts.append(
            f'<div class="featured-expert {is_sel}">'
            f'<img src="data:image/png;base64,{b64}" title="{inf["name"]}">'
            f'<span class="name">{first_name}</span></div>'
        )

    st.markdown(
        f'<div class="featured-experts">{"".join(featured_html_parts)}</div>',
        unsafe_allow_html=True,
    )

    # Selection buttons (Streamlit needs real buttons for state)
    # Collective wisdom + featured experts in a row
    button_items = [{"slug": None, "label": "All"}] + [
        {"slug": inf["slug"], "label": inf["name"].split()[0]}
        for inf in featured
    ]

    cols = st.columns(len(button_items))
    for i, item in enumerate(button_items):
        with cols[i]:
            key = "select_cw" if item["slug"] is None else f"sel_{item['slug']}"
            if st.button(item["label"], key=key, use_container_width=True):
                switch_persona(item["slug"])
                st.rerun()

    # "Browse all experts" popover
    with st.popover("Browse all experts", use_container_width=True):
        search = st.text_input("Search experts", key="expert_search", placeholder="Type a name...")

        filtered = influencers
        if search:
            search_lower = search.lower()
            filtered = [
                inf for inf in influencers
                if search_lower in inf["name"].lower()
                or search_lower in inf.get("specialty", "").lower()
            ]

        for inf in filtered:
            persona = get_persona(inf["slug"])
            confidence = ""
            if persona:
                conf = persona.get("confidence", "medium")
                label = get_confidence_label(conf)
                confidence = f" · {label}"

            if st.button(
                f"{inf['name']}{confidence}",
                key=f"pop_{inf['slug']}",
                use_container_width=True,
            ):
                switch_persona(inf["slug"])
                st.rerun()


# ── Active Context Bar ─────────────────────────────────

def _render_context_bar() -> None:
    """Show active filters: selected expert and/or stage as dismissable chips."""
    selected = st.session_state.get("selected_persona")
    stage = st.session_state.get("selected_stage_group", "All")
    methodology = st.session_state.get("selected_methodology")

    if not selected and stage == "All" and not methodology:
        return

    chips = []

    if selected:
        name = get_influencer_name(selected)
        b64 = get_avatar_base64(selected)
        chips.append(
            f'<span class="context-chip">'
            f'<img src="data:image/png;base64,{b64}">'
            f'{name}</span>'
        )

    if stage != "All":
        chips.append(f'<span class="context-chip">{stage}</span>')

    if methodology:
        chips.append(f'<span class="context-chip">{methodology}</span>')

    st.markdown(
        f'<div class="context-bar">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


# ── Coaching Mode Indicator ────────────────────────────

def _render_coaching_mode() -> None:
    """Show 'Coaching as [Expert]' indicator when in persona mode."""
    selected = st.session_state.get("selected_persona")
    if not selected:
        return

    name = get_influencer_name(selected)
    b64 = get_avatar_base64(selected)
    persona = get_persona(selected)

    sublabel = ""
    if persona:
        conf = persona.get("confidence", "medium")
        label = get_confidence_label(conf)
        sublabel = f'<span class="sublabel">{label} profile</span>'

    st.markdown(
        f"""<div class="coaching-mode">
    <img src="data:image/png;base64,{b64}" alt="{name}">
    <div>
        <span class="label">Coaching as {name}</span><br>
        {sublabel}
    </div>
</div>""",
        unsafe_allow_html=True,
    )


# ── Filters (stage + methodology) ─────────────────────

@st.fragment
def _render_filters(insights: list[dict]) -> None:
    """Render stage and methodology filters."""
    col1, col2 = st.columns(2)

    with col1:
        counts = get_stage_counts(insights)
        options = stage_group_options(counts)
        current = st.session_state.get("selected_stage_group", "All")
        current_display = value_to_stage_option(current, options)

        selected = st.selectbox(
            "Deal stage",
            options=options,
            index=options.index(current_display) if current_display in options else 0,
            key="coach_stage_filter",
            label_visibility="collapsed",
        )
        new_value = stage_option_to_value(selected)
        if new_value != current:
            st.session_state.selected_stage_group = new_value
            st.rerun()

    with col2:
        methodologies = load_methodologies()
        if methodologies:
            method_options = ["All methodologies"] + [m["name"] for m in methodologies]
            current_method = st.session_state.get("selected_methodology")
            current_idx = 0
            if current_method:
                for i, m in enumerate(methodologies):
                    if m["id"] == current_method:
                        current_idx = i + 1
                        break

            selected_method = st.selectbox(
                "Methodology",
                options=method_options,
                index=current_idx,
                key="coach_method_filter",
                label_visibility="collapsed",
            )
            if selected_method == "All methodologies":
                if st.session_state.get("selected_methodology"):
                    st.session_state.selected_methodology = None
                    st.rerun()
            else:
                for m in methodologies:
                    if m["name"] == selected_method:
                        if st.session_state.get("selected_methodology") != m["id"]:
                            st.session_state.selected_methodology = m["id"]
                            st.rerun()
                        break


# ── Stage Summary ─────────────────────────────────────

def _render_stage_summary(stage_group: str, insights: list[dict]) -> None:
    """Show a golden insight for the active stage filter.

    Calls Claude to synthesize a 12-word actionable tip, cached in session state.
    """
    if stage_group == "All":
        return

    cache = st.session_state.get("stage_insights", {})

    if stage_group not in cache:
        tip = synthesize_stage_insight(stage_group, insights)
        cache[stage_group] = tip
        st.session_state.stage_insights = cache

    tip = cache[stage_group]
    st.markdown(
        f'<div class="stage-summary">'
        f'<span class="stage-summary-label">{stage_group}</span>'
        f'<span class="stage-summary-tip">{tip}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Welcome State ──────────────────────────────────────

def _render_welcome_state() -> None:
    """Render the welcome state with persona-specific or generic suggestions."""
    selected = st.session_state.get("selected_persona")
    persona = get_persona(selected) if selected else None

    if persona and persona.get("suggested_questions"):
        # Persona-specific suggestions
        questions = persona["suggested_questions"][:4]
        name = persona.get("name", "Expert")
        st.markdown(
            f'<p style="text-align:center;color:var(--text-muted);font-size:0.85rem;margin-bottom:8px">Ask {name}:</p>',
            unsafe_allow_html=True,
        )
    else:
        # Generic suggestions
        questions = [
            "How do I handle price objections?",
            "My prospect went silent after the demo",
            "Discovery questions for a CFO meeting",
            "Creating urgency without being pushy",
        ]

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    icons = ["💰", "👻", "🎯", "⏰"]
    for i, question in enumerate(questions):
        icon = icons[i] if i < len(icons) else "💡"
        with col1 if i % 2 == 0 else col2:
            if st.button(
                f"{icon} {question}",
                key=f"suggestion_{i}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.prefill_question = question
                st.rerun()


# ── Chat Processing ────────────────────────────────────

def _process_message(prompt: str, insights: list[dict]) -> dict:
    """Process a user message and return the assistant response dict."""
    selected = st.session_state.get("selected_persona")
    persona = get_persona(selected) if selected else None

    # Find relevant insights
    relevant = find_relevant_insights(
        insights, prompt, expert_slug=selected,
    )

    if not relevant:
        if selected:
            name = get_influencer_name(selected)
            response_text = f"I couldn't find specific insights from {name} matching your question. Try switching to 'All Experts' for broader advice."
        else:
            response_text = "I couldn't find specific insights matching your question. Try rephrasing or ask about: discovery, objections, closing, negotiation, or prospecting."
        return {"role": "assistant", "content": response_text, "sources": []}

    context = build_context(relevant)
    response_text = get_coaching_advice(
        prompt,
        context,
        st.session_state.messages[:-1] if st.session_state.messages else [],
        persona=persona,
    )

    sources = relevant[:5]
    return {"role": "assistant", "content": response_text, "sources": sources}


# ── Main ───────────────────────────────────────────────

def main() -> None:
    sync_query_params()

    _render_header()
    _render_expert_selector()

    has_api_key = bool(get_anthropic_key())

    # Load and filter insights
    all_insights = load_insights()
    if not all_insights and has_api_key:
        st.warning("No insights loaded. Check database or Airtable connection.")

    # Apply filters
    filtered = filter_insights(
        all_insights,
        expert_slug=st.session_state.get("selected_persona"),
        stage_group=st.session_state.get("selected_stage_group", "All"),
        methodology_id=st.session_state.get("selected_methodology"),
    )

    # Sync URL params with current filter state
    update_query_params()

    # Context bar + coaching mode + stage summary
    _render_context_bar()
    _render_coaching_mode()
    _render_stage_summary(
        st.session_state.get("selected_stage_group", "All"),
        filtered,
    )

    # Stage/methodology filters (shown when conversation active)
    has_conversation = bool(st.session_state.get("messages"))
    if has_conversation:
        _render_filters(all_insights)

    # Handle prefilled question
    prefill = st.session_state.pop("prefill_question", None)

    if not st.session_state.messages and not prefill:
        _render_welcome_state()
    elif prefill and has_api_key:
        st.session_state.messages.append({"role": "user", "content": prefill})
        try:
            st.session_state.conversation_title = generate_conversation_title(prefill)
        except Exception:
            words = prefill.split()[:5]
            st.session_state.conversation_title = " ".join(words) + "..."

        response = _process_message(prefill, filtered)
        st.session_state.messages.append(response)
        st.rerun()
    elif st.session_state.messages:
        # Show conversation title
        st.markdown(
            f'<div class="conversation-title">{st.session_state.conversation_title}</div>',
            unsafe_allow_html=True,
        )
        render_chat_messages(st.session_state.messages)

    # API key warning (shown after UI, not blocking)
    if not has_api_key:
        st.info("Add ANTHROPIC_API_KEY to secrets to enable chat. UI preview mode active.")

    # Chat input
    placeholder = "Describe your sales situation..."
    selected = st.session_state.get("selected_persona")
    if selected:
        name = get_influencer_name(selected)
        placeholder = f"Ask {name} about..."

    if prompt := st.chat_input(placeholder):
        if not has_api_key:
            st.error("Chat requires ANTHROPIC_API_KEY. Please configure secrets.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    if len(st.session_state.messages) == 1:
                        try:
                            st.session_state.conversation_title = generate_conversation_title(prompt)
                        except Exception:
                            words = prompt.split()[:5]
                            st.session_state.conversation_title = " ".join(words) + "..."

                    response = _process_message(prompt, filtered)

            st.session_state.messages.append(response)
            st.rerun()

    # Clear conversation button
    if st.session_state.messages:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Clear conversation", type="secondary", use_container_width=True):
                reset_conversation()
                st.rerun()

    # Footer
    influencer_count = len(load_influencers())
    st.markdown(
        f'<div class="footer-text">Powered by Claude AI · {len(all_insights)} insights from {influencer_count} experts</div>',
        unsafe_allow_html=True,
    )


main()
