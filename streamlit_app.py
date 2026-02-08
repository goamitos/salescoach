"""Sales Coach AI — Entry point.

Three-page multipage app: Coach (chat), Experts (directory), Insights (browse).
Uses st.navigation / st.Page (requires streamlit>=1.36.0).
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.state import init_session_state

# Page config — must be first Streamlit command
st.set_page_config(
    page_title="Sales Coach AI",
    page_icon="assets/avatars/30mpc.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load CSS design system once (applies to all pages)
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# Initialize shared session state
init_session_state()

# Navigation
coach_page = st.Page("pages/1_coach.py", title="Coach", icon=":material/chat:", default=True)
experts_page = st.Page("pages/2_experts.py", title="Experts", icon=":material/people:")
insights_page = st.Page("pages/3_insights.py", title="Insights", icon=":material/lightbulb:")

pg = st.navigation([coach_page, experts_page, insights_page])
pg.run()
