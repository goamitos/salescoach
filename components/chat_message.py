"""Enhanced chat message rendering with inline source cards."""
from __future__ import annotations

import streamlit as st

from components.insight_card import source_card_html


def render_chat_messages(messages: list[dict]) -> None:
    """Render all chat messages with source cards."""
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            sources = message.get("sources")
            if sources:
                # Render inline source cards instead of expanders
                cards_html = "".join(source_card_html(s) for s in sources)
                st.markdown(
                    f'<div style="margin-top:8px">{cards_html}</div>',
                    unsafe_allow_html=True,
                )
