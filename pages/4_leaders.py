"""Leadership Hub — VP Sales & CRO Insights.

Browse, search, and get AI coaching from leadership-tagged content.
"""
from __future__ import annotations

import json

import streamlit as st

from utils.data import (
    load_leader_insights,
    load_insights,
    get_leader_stats,
    filter_insights,
)
from utils.search import find_relevant_insights, build_context
from utils.ai import get_coaching_advice

# ── Load Data ─────────────────────────────────────────
leader_insights = load_leader_insights()
all_insights = load_insights()
stats = get_leader_stats(leader_insights)

# ── Header ────────────────────────────────────────────
st.markdown("## Leadership Hub")
st.markdown(f"**{stats['total']}** insights for VP Sales & CRO roles (from {len(all_insights)} total)")

# ── Stats Dashboard ───────────────────────────────────
if stats["total"] > 0:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### By Deal Stage")
        for stage, count in list(stats["by_stage"].items())[:8]:
            pct = count / stats["total"] * 100
            st.markdown(f"**{stage}**: {count} ({pct:.0f}%)")

    with col2:
        st.markdown("#### Top Contributors")
        for name, count in list(stats["by_influencer"].items())[:8]:
            st.markdown(f"**{name}**: {count} insights")

    if stats["top_keywords"]:
        st.markdown("#### Top Keywords")
        kw_display = ", ".join(f"**{kw}** ({c})" for kw, c in stats["top_keywords"][:12])
        st.markdown(kw_display)

    st.divider()

# ── Filters & Search ──────────────────────────────────
col_search, col_stage, col_expert = st.columns([3, 1, 1])

with col_search:
    search_query = st.text_input("Search leadership insights", placeholder="pipeline review, forecast, coaching...")

with col_stage:
    stages = ["All"] + list(stats["by_stage"].keys())
    selected_stage = st.selectbox("Stage", stages)

with col_expert:
    influencers = ["All"] + list(stats["by_influencer"].keys())
    selected_expert = st.selectbox("Expert", influencers)

# Apply filters
filtered = leader_insights
if search_query:
    query_lower = search_query.lower()
    keywords = [w for w in query_lower.split() if len(w) > 2]
    filtered = [
        i for i in filtered
        if any(
            kw in (i.get("key_insight", "") + " " +
                   i.get("best_quote", "") + " " +
                   " ".join(i.get("keywords") or []) + " " +
                   " ".join(i.get("tactical_steps") or [])).lower()
            for kw in keywords
        )
    ]
if selected_stage != "All":
    filtered = [i for i in filtered if i.get("primary_stage") == selected_stage]
if selected_expert != "All":
    filtered = [i for i in filtered if i.get("influencer_name") == selected_expert]

st.markdown(f"**{len(filtered)}** insights matching filters")

# ── Browse Results ────────────────────────────────────
for insight in filtered[:30]:
    name = insight.get("influencer_name", "Unknown")
    key = insight.get("key_insight", "")
    audience = insight.get("target_audience", [])
    if isinstance(audience, str):
        try:
            audience = json.loads(audience)
        except json.JSONDecodeError:
            audience = []
    confidence = insight.get("audience_confidence", 0)
    stage = insight.get("primary_stage", "General")

    with st.expander(f"**{name}** — {key[:80]}{'...' if len(key) > 80 else ''}", expanded=False):
        st.markdown(f"**Stage:** {stage} | **Audience:** {', '.join(audience)} ({confidence:.0%})")
        st.markdown(f"**Insight:** {key}")

        steps = insight.get("tactical_steps") or []
        if steps:
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except json.JSONDecodeError:
                    steps = [steps]
            st.markdown("**Tactical Steps:**")
            for step in steps:
                st.markdown(f"- {step}")

        quote = insight.get("best_quote", "")
        if quote:
            st.markdown(f'> "{quote}"')

        url = insight.get("source_url", "")
        if url:
            st.markdown(f"[Source]({url})")

# ── AI Q&A ────────────────────────────────────────────
st.divider()
st.markdown("### Ask About Leadership")

leader_question = st.text_input(
    "Ask a leadership question",
    placeholder="How should I structure my first 90 days as a new VP Sales?",
    key="leader_question",
)

if leader_question and st.button("Get Leadership Advice", key="leader_ask_btn"):
    with st.spinner("Synthesizing leadership insights..."):
        relevant = find_relevant_insights(leader_insights, leader_question, top_n=8)
        if relevant:
            context = build_context(relevant)
            advice = get_coaching_advice(
                leader_question, context, chat_history=[], persona=None,
            )
            st.markdown(advice)

            with st.expander("Sources used"):
                for r in relevant:
                    name = r.get("influencer_name", "Unknown")
                    insight_text = r.get("key_insight", "")[:80]
                    st.markdown(f"- **{name}**: {insight_text}...")
        else:
            st.warning("No matching leadership insights found. Try different keywords.")
