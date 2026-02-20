"""Sales Coach AI — Single-page app with horizontal tab navigation.

Three modes: Coach (chat), Experts (directory), Insights (browse).
Navigation via horizontal tabs in the header.
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
)

# Load CSS design system once
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# Initialize shared session state
init_session_state()

# ── Tab Navigation (Horizontal) ────────────────────────────────────

# Get current tab from URL params or default to "coach"
if "page" not in st.query_params:
    st.query_params["page"] = "coach"
current_tab = st.query_params.get("page", "coach")

# Hide the default Streamlit sidebar and render horizontal tab navigation
st.markdown("""
<style>
/* Hide default Streamlit sidebar */
[data-testid="stSidebar"] {
    display: none;
}
section[data-testid="stSidebar"] {
    display: none;
}

.nav-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid rgba(250, 250, 250, 0.1);
    margin-bottom: 2rem;
    padding: 0 2rem;
}
.nav-tab {
    padding: 1rem 2rem;
    font-size: 1rem;
    font-weight: 500;
    color: rgba(250, 250, 250, 0.6);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.nav-tab:hover {
    color: rgba(250, 250, 250, 0.9);
    background: rgba(250, 250, 250, 0.05);
}
.nav-tab.active {
    color: #fff;
    border-bottom-color: #7c3aed;
}
.nav-icon {
    margin-right: 0.5rem;
    font-size: 1.2rem;
}
</style>
""", unsafe_allow_html=True)

# Tab buttons (using Streamlit columns for click handling)
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 5])

with col1:
    if st.button("💬 Coach", key="tab_coach", use_container_width=True):
        st.query_params["page"] = "coach"
        st.rerun()

with col2:
    if st.button("👥 Experts", key="tab_experts", use_container_width=True):
        st.query_params["page"] = "experts"
        st.rerun()

with col3:
    if st.button("💡 Insights", key="tab_insights", use_container_width=True):
        st.query_params["page"] = "insights"
        st.rerun()

with col4:
    if st.button("👔 Leaders", key="tab_leaders", use_container_width=True):
        st.query_params["page"] = "leaders"
        st.rerun()

# Add visual indicator for active tab
st.markdown(f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const tabs = document.querySelectorAll('[data-testid^="tab_"]');
    tabs.forEach(tab => {{
        if (tab.textContent.toLowerCase().includes('{current_tab}')) {{
            tab.classList.add('active');
        }}
    }});
}});
</script>
""", unsafe_allow_html=True)

# ── Render Selected Page ───────────────────────────────────────────

if current_tab == "coach":
    # Import and execute coach page
    import importlib.util
    spec = importlib.util.spec_from_file_location("coach_page", "pages/1_coach.py")
    coach_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coach_module)

elif current_tab == "experts":
    # Import and execute experts page
    import importlib.util
    spec = importlib.util.spec_from_file_location("experts_page", "pages/2_experts.py")
    experts_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experts_module)

elif current_tab == "insights":
    # Import and execute insights page
    import importlib.util
    spec = importlib.util.spec_from_file_location("insights_page", "pages/3_insights.py")
    insights_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(insights_module)

elif current_tab == "leaders":
    # Import and execute leaders page
    import importlib.util
    spec = importlib.util.spec_from_file_location("leaders_page", "pages/4_leaders.py")
    leaders_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(leaders_module)
