"""
Sales Coach - AI-Powered Q&A Web App

A Streamlit app that provides natural language Q&A over
curated sales wisdom from top LinkedIn/YouTube sales voices.

Run locally:
    streamlit run streamlit_app.py

Deploy to Streamlit Cloud:
    1. Push to GitHub
    2. Connect repo at share.streamlit.io
    3. Add secrets in Streamlit Cloud dashboard
"""
import re
import streamlit as st
from pyairtable import Api
import anthropic

# Page config
st.set_page_config(
    page_title="Sales Coach AI",
    page_icon="🎯",
    layout="centered",
)

# Stage-related keywords for better matching
STAGE_KEYWORDS = {
    "discovery": ["discovery", "discover", "question", "ask", "learn", "understand", "needs"],
    "prospecting": ["prospect", "cold", "outreach", "email", "call", "reach", "sdr"],
    "negotiation": ["negotiate", "negotiation", "price", "pricing", "discount", "contract"],
    "closing": ["close", "closing", "deal", "sign", "commit", "decision", "won"],
    "objection": ["objection", "pushback", "concern", "hesitation", "resist", "but"],
    "demo": ["demo", "presentation", "present", "show", "demonstrate"],
    "qualification": ["qualify", "qualification", "fit", "budget", "authority", "timeline", "bant"],
    "followup": ["follow", "followup", "silent", "ghost", "respond", "reply"],
}


def get_secrets():
    """Get secrets from Streamlit secrets or environment."""
    try:
        return {
            "anthropic_key": st.secrets["ANTHROPIC_API_KEY"],
            "airtable_key": st.secrets["AIRTABLE_API_KEY"],
            "airtable_base": st.secrets["AIRTABLE_BASE_ID"],
            "airtable_table": st.secrets.get("AIRTABLE_TABLE_NAME", "Sales Wisdom"),
        }
    except Exception:
        # Fallback to environment variables for local dev
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return {
            "anthropic_key": os.getenv("ANTHROPIC_API_KEY"),
            "airtable_key": os.getenv("AIRTABLE_API_KEY"),
            "airtable_base": os.getenv("AIRTABLE_BASE_ID"),
            "airtable_table": os.getenv("AIRTABLE_TABLE_NAME", "Sales Wisdom"),
        }


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_records(_airtable_key: str, _base_id: str, _table_name: str):
    """Fetch all records from Airtable (cached)."""
    base_id = _base_id.split("/")[0]
    api = Api(_airtable_key)
    table = api.table(base_id, _table_name)
    return table.all()


def score_record(record: dict, user_keywords: list[str], matched_stages: list[str]) -> float:
    """Score a record based on keyword and stage matches."""
    fields = record.get("fields", {})

    insight = (fields.get("Key Insight") or "").lower()
    stage = (fields.get("Primary Stage") or "").lower()
    secondary = (fields.get("Secondary Stages") or "").lower()
    steps = (fields.get("Tactical Steps") or "").lower()
    keywords = (fields.get("Keywords") or "").lower()
    situations = (fields.get("Situation Examples") or "").lower()
    quote = (fields.get("Best Quote") or "").lower()

    combined = f"{insight} {stage} {secondary} {steps} {keywords} {situations} {quote}"

    score = 0.0

    for kw in user_keywords:
        if kw in combined:
            score += 2

    for matched_stage in matched_stages:
        if matched_stage in stage or matched_stage in secondary:
            score += 3

    original_score = fields.get("Relevance Score") or 0
    score += original_score / 5

    return score


def find_relevant_records(records: list[dict], scenario: str, top_n: int = 5) -> list[dict]:
    """Find the most relevant records for a given scenario."""
    user_keywords = [
        word.lower()
        for word in re.findall(r'\w+', scenario)
        if len(word) > 3
    ]

    matched_stages = []
    scenario_lower = scenario.lower()
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(kw in scenario_lower for kw in keywords):
            matched_stages.append(stage)

    scored = []
    for record in records:
        score = score_record(record, user_keywords, matched_stages)
        if score > 0:
            scored.append((record, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [record for record, _ in scored[:top_n]]


def build_context(records: list[dict]) -> str:
    """Build context string from relevant records."""
    parts = []
    for record in records:
        fields = record.get("fields", {})
        influencer = fields.get("Influencer") or "Unknown"
        stage = fields.get("Primary Stage") or "General"
        insight = fields.get("Key Insight") or ""
        steps = fields.get("Tactical Steps") or ""
        situations = fields.get("Situation Examples") or ""
        quote = fields.get("Best Quote") or ""

        part = f"**{influencer}** ({stage}):\nInsight: {insight}"
        if steps:
            part += f"\nSteps: {steps}"
        if situations:
            part += f"\nWhen to use: {situations}"
        if quote:
            part += f"\nKey quote: \"{quote}\""
        parts.append(part)

    return "\n\n---\n\n".join(parts)


def get_coaching_advice(anthropic_key: str, scenario: str, context: str) -> str:
    """Call Claude API to synthesize coaching advice."""
    client = anthropic.Anthropic(api_key=anthropic_key)

    system_prompt = """You are an expert sales coach who synthesizes wisdom from top sales leaders to provide actionable advice.

Your role is to:
1. Understand the salesperson's specific situation
2. Draw from the provided expert insights to craft personalized advice
3. Give concrete, actionable steps (not generic platitudes)
4. Reference which expert's approach you're drawing from
5. Keep advice focused and practical (3-5 key points)

Format your response with:
- A brief acknowledgment of their situation
- Numbered actionable recommendations
- Brief attribution to the relevant experts"""

    user_prompt = f"""A salesperson describes their situation:

"{scenario}"

Based on these expert insights from top sales leaders:

{context}

Provide specific, actionable coaching advice. Reference which expert's wisdom you're drawing from when relevant."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text


def main():
    # Header
    st.title("🎯 Sales Coach AI")
    st.markdown("*Get personalized coaching from top sales voices*")

    # Get secrets
    secrets = get_secrets()

    if not all([secrets["anthropic_key"], secrets["airtable_key"], secrets["airtable_base"]]):
        st.error("Missing API credentials. Please configure secrets.")
        st.markdown("""
        **For Streamlit Cloud**: Add secrets in your app settings.

        **For local development**: Create a `.env` file with:
        ```
        ANTHROPIC_API_KEY=your_key
        AIRTABLE_API_KEY=your_key
        AIRTABLE_BASE_ID=your_base_id
        AIRTABLE_TABLE_NAME=Sales Wisdom
        ```
        """)
        return

    # Load records
    try:
        with st.spinner("Loading knowledge base..."):
            records = fetch_records(
                secrets["airtable_key"],
                secrets["airtable_base"],
                secrets["airtable_table"]
            )
        st.caption(f"📚 {len(records)} insights loaded")
    except Exception as e:
        st.error(f"Failed to load Airtable data: {e}")
        return

    # Input section
    st.markdown("---")
    scenario = st.text_area(
        "Describe your sales situation or question:",
        placeholder="e.g., I'm meeting with a skeptical CFO tomorrow who keeps pushing back on price. What should I focus on?",
        height=100,
    )

    # Example questions
    with st.expander("💡 Example questions"):
        st.markdown("""
        - "I'm in discovery with a CFO who seems distracted"
        - "The prospect went silent after my demo. How do I follow up?"
        - "How do I handle 'we don't have budget' objections?"
        - "What questions should I ask to uncover the real decision maker?"
        - "How do I create urgency without being pushy?"
        """)

    # Submit button
    if st.button("Get Coaching Advice", type="primary", use_container_width=True):
        if not scenario.strip():
            st.warning("Please describe your situation first.")
            return

        # Find relevant records
        with st.spinner("Searching knowledge base..."):
            relevant = find_relevant_records(records, scenario)

        if not relevant:
            st.warning("""
            No matching insights found. Try:
            - Using different keywords
            - Being more specific about the sales stage
            - Topics: discovery, objections, closing, negotiation, prospecting
            """)
            return

        # Get advice
        with st.spinner("Synthesizing coaching advice..."):
            context = build_context(relevant)
            advice = get_coaching_advice(secrets["anthropic_key"], scenario, context)

        # Display advice
        st.markdown("---")
        st.markdown("## 🎯 Coaching Advice")
        st.markdown(advice)

        # Display sources
        st.markdown("---")
        st.markdown("### 📚 Sources Used")

        for record in relevant:
            fields = record.get("fields", {})
            influencer = fields.get("Influencer") or "Unknown"
            stage = fields.get("Primary Stage") or "General"
            url = fields.get("Source URL") or ""
            insight = fields.get("Key Insight") or ""

            short_insight = insight[:100] + "..." if len(insight) > 100 else insight

            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{influencer}** ({stage})")
                    st.caption(short_insight)
                with col2:
                    if url:
                        st.link_button("View Source", url, use_container_width=True)

    # Footer
    st.markdown("---")
    st.caption("Powered by Claude AI • Data from LinkedIn & YouTube sales voices")


if __name__ == "__main__":
    main()
