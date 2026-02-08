"""Session state initialization and management."""
from __future__ import annotations

from typing import Optional

import streamlit as st


def init_session_state() -> None:
    """Initialize all session state variables with defaults."""
    defaults = {
        # Chat
        "messages": [],
        "conversation_title": "New Conversation",
        "prefill_question": None,

        # Expert selection
        "selected_persona": None,  # None = Collective Wisdom (all experts)

        # Stage filter
        "selected_stage_group": "All",

        # Methodology filter
        "selected_methodology": None,

        # Stage insights cache (synthesized golden insights per stage)
        "stage_insights": {},
    }

    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_conversation() -> None:
    """Clear conversation and reset related state."""
    st.session_state.messages = []
    st.session_state.conversation_title = "New Conversation"


def switch_persona(slug: Optional[str]) -> None:
    """Switch to a new persona (or back to collective wisdom).

    Clears the conversation when switching experts, as recommended
    by the persona plan for voice consistency.
    """
    if slug != st.session_state.get("selected_persona"):
        st.session_state.selected_persona = slug
        reset_conversation()


def set_prefill_and_navigate(question: str) -> None:
    """Set a prefill question for the Coach page.

    Used by Insights page "Ask about this" and Experts page suggestions.
    """
    st.session_state.prefill_question = question


def sync_query_params() -> None:
    """Read URL query params and apply to session state (once per session).

    Supports: ?expert=<slug>&stage=<stage_group>&methodology=<id>
    Only applies params that haven't been overridden by user interaction.
    """
    if st.session_state.get("_query_params_synced"):
        return

    params = st.query_params

    expert = params.get("expert")
    if expert and st.session_state.get("selected_persona") is None:
        st.session_state.selected_persona = expert

    stage = params.get("stage")
    if stage and st.session_state.get("selected_stage_group", "All") == "All":
        st.session_state.selected_stage_group = stage

    methodology = params.get("methodology")
    if methodology and st.session_state.get("selected_methodology") is None:
        st.session_state.selected_methodology = methodology

    st.session_state._query_params_synced = True


def update_query_params() -> None:
    """Write current session state filters back to URL query params.

    Keeps the browser URL in sync so links are shareable.
    """
    params = {}

    expert = st.session_state.get("selected_persona")
    if expert:
        params["expert"] = expert

    stage = st.session_state.get("selected_stage_group", "All")
    if stage and stage != "All":
        params["stage"] = stage

    methodology = st.session_state.get("selected_methodology")
    if methodology:
        params["methodology"] = methodology

    st.query_params.update(params)

    # Clear params that are no longer active
    for key in ["expert", "stage", "methodology"]:
        if key not in params and key in st.query_params:
            del st.query_params[key]
