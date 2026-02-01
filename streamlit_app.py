"""
Sales Coach - AI-Powered Chat Interface

A Streamlit app with:
- Claude.ai-inspired chat interface with conversation titles
- Compact header with influencer avatars
- Single-accordion stage navigation
- 1-line synthesized insights per stage

Run locally:
    streamlit run streamlit_app.py

Deploy to Streamlit Cloud:
    1. Push to GitHub
    2. Connect repo at share.streamlit.io
    3. Add secrets in Streamlit Cloud dashboard
"""

import base64
import re
from pathlib import Path
import streamlit as st
from pyairtable import Api
import anthropic

# Page config - must be first Streamlit command
st.set_page_config(
    page_title="Sales Coach AI",
    page_icon="assets/avatars/30mpc.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for Claude.ai-inspired styling
st.markdown(
    """
<style>
/* Remove default Streamlit padding at top */
.block-container {
    padding-top: 2.5rem !important;
}

/* Header styling */
.header-title {
    padding: 0.5rem 0;
    margin-bottom: 0.5rem;
}
.header-title h1 {
    margin: 0;
    font-size: 1.8rem;
    font-weight: 700;
}
.header-title p {
    margin: 0;
    color: #888;
    font-size: 0.9rem;
}

/* Avatar image hover effects */
.avatar-img:hover {
    opacity: 1 !important;
    transform: scale(1.1);
}

/* Conversation title */
.conversation-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #666;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #eee;
}

/* Chat message styling - Claude.ai inspired */
.stChatMessage {
    padding: 0.75rem 1rem !important;
    border-radius: 18px !important;
    margin-bottom: 0.5rem !important;
}
.stChatMessage[data-testid="user-message"] {
    background: linear-gradient(135deg, #2D5A3D 0%, #1E3F2B 100%) !important;
    margin-left: 15% !important;
}
.stChatMessage[data-testid="assistant-message"] {
    background: transparent !important;
    margin-right: 10% !important;
}

/* Sources link styling */
.sources-toggle {
    font-size: 0.85rem;
    color: #666;
    cursor: pointer;
    margin-top: 0.5rem;
}
.sources-toggle:hover {
    color: #4ECDC4;
}

/* Stage accordion styling */
.stage-group-btn {
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: transparent;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.95rem;
    transition: background 0.2s;
}
.stage-group-btn:hover {
    background: rgba(78, 205, 196, 0.1);
}
.stage-insight {
    font-style: italic;
    color: inherit;
    opacity: 0.8;
    font-size: 0.9rem;
    padding: 0.25rem 0.75rem 0.5rem 1.5rem;
}
.nested-stage {
    padding-left: 1.5rem;
    font-size: 0.9rem;
}

/* Mindset callout - works in both light and dark mode */
.mindset-callout {
    background: rgba(78, 205, 196, 0.1);
    border-left: 4px solid #4ECDC4;
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 1rem;
}
.mindset-callout strong {
    color: #4ECDC4;
}

/* Clear chat button */
.clear-chat-btn {
    opacity: 0.6;
    font-size: 0.85rem;
}
.clear-chat-btn:hover {
    opacity: 1;
}
</style>
""",
    unsafe_allow_html=True,
)

# Constants
PROJECT_ROOT = Path(__file__).parent

# Collective Wisdom avatar (displayed first, represents all experts)
COLLECTIVE_WISDOM = {"name": "Collective Wisdom", "slug": "collective-wisdom"}

# Influencer data for avatars
INFLUENCERS = [
    {"name": "30MPC", "slug": "30mpc"},
    {"name": "Armand Farrokh", "slug": "armand-farrokh"},
    {"name": "Nick Cegelski", "slug": "nick-cegelski"},
    {"name": "Samantha McKenna", "slug": "samantha-mckenna"},
    {"name": "Ian Koniak", "slug": "ian-koniak"},
    {"name": "Daniel Disney", "slug": "daniel-disney"},
    {"name": "Will Aitken", "slug": "will-aitken"},
    {"name": "Devin Reed", "slug": "devin-reed"},
    {"name": "Florin Tatulea", "slug": "florin-tatulea"},
    {"name": "Gal Aga", "slug": "gal-aga"},
    {"name": "Nate Nasralla", "slug": "nate-nasralla"},
    {"name": "Morgan J Ingram", "slug": "morgan-j-ingram"},
    {"name": "Kyle Coleman", "slug": "kyle-coleman"},
]

# Stage groups for sidebar
STAGE_GROUPS = {
    "Planning & Research": [
        "Territory Planning",
        "Account Research",
        "Stakeholder Mapping",
    ],
    "Outreach & Contact": [
        "Outreach Strategy",
        "Initial Contact",
    ],
    "Discovery & Analysis": [
        "Discovery",
        "Needs Analysis",
    ],
    "Present & Prove Value": [
        "Demo & Presentation",
        "Business Case Development",
        "Proof of Value",
    ],
    "Close & Grow": [
        "RFP/RFQ Response",
        "Procurement & Negotiation",
        "Closing",
        "Onboarding & Expansion",
    ],
}

# Stage-related keywords for matching
STAGE_KEYWORDS = {
    "discovery": [
        "discovery",
        "discover",
        "question",
        "ask",
        "learn",
        "understand",
        "needs",
    ],
    "prospecting": ["prospect", "cold", "outreach", "email", "call", "reach", "sdr"],
    "negotiation": [
        "negotiate",
        "negotiation",
        "price",
        "pricing",
        "discount",
        "contract",
    ],
    "closing": ["close", "closing", "deal", "sign", "commit", "decision", "won"],
    "objection": ["objection", "pushback", "concern", "hesitation", "resist", "but"],
    "demo": ["demo", "presentation", "present", "show", "demonstrate"],
    "qualification": [
        "qualify",
        "qualification",
        "fit",
        "budget",
        "authority",
        "timeline",
        "bant",
    ],
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
        import os
        from dotenv import load_dotenv

        load_dotenv()
        return {
            "anthropic_key": os.getenv("ANTHROPIC_API_KEY"),
            "airtable_key": os.getenv("AIRTABLE_API_KEY"),
            "airtable_base": os.getenv("AIRTABLE_BASE_ID"),
            "airtable_table": os.getenv("AIRTABLE_TABLE_NAME", "Sales Wisdom"),
        }


@st.cache_data(ttl=300)
def fetch_records(_airtable_key: str, _base_id: str, _table_name: str):
    """Fetch all records from Airtable (cached)."""
    base_id = _base_id.split("/")[0]
    api = Api(_airtable_key)
    table = api.table(base_id, _table_name)
    return table.all()


def score_record(
    record: dict, user_keywords: list[str], matched_stages: list[str]
) -> float:
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


def find_relevant_records(
    records: list[dict], scenario: str, top_n: int = 5
) -> list[dict]:
    """Find the most relevant records for a given scenario."""
    user_keywords = [
        word.lower() for word in re.findall(r"\w+", scenario) if len(word) > 3
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
            part += f'\nKey quote: "{quote}"'
        parts.append(part)

    return "\n\n---\n\n".join(parts)


def get_coaching_advice(
    anthropic_key: str,
    scenario: str,
    context: str,
    chat_history: list,
    selected_persona: str = None,
) -> str:
    """Call Claude API to synthesize coaching advice with conversation context."""
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
- Brief attribution to the relevant experts

If the user is following up on a previous question, reference and build upon your earlier advice.
Keep responses conversational but professional."""

    # Modify system prompt for selected persona
    if selected_persona:
        persona_name = get_influencer_name(selected_persona)
        system_prompt += f"""

IMPORTANT: You are channeling the coaching style of {persona_name}.
Draw primarily from their specific insights and speak in their voice.
Reference their specific frameworks and approaches.
Make the advice feel like it's coming directly from {persona_name}."""

    # Build messages with chat history for context
    messages = []

    # Include last 3 exchanges for context
    history_to_include = chat_history[-6:] if len(chat_history) > 6 else chat_history
    for msg in history_to_include:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question with context
    user_prompt = f"""A salesperson asks:

"{scenario}"

Based on these expert insights from top sales leaders:

{context}

Provide specific, actionable coaching advice. Reference which expert's wisdom you're drawing from when relevant."""

    messages.append({"role": "user", "content": user_prompt})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text


def get_records_for_stage_group(records: list[dict], stages: list[str]) -> list[dict]:
    """Get all records that match any of the given stages."""
    matching = []
    for record in records:
        fields = record.get("fields", {})
        primary = fields.get("Primary Stage") or ""
        secondary = fields.get("Secondary Stages") or ""

        for stage in stages:
            if stage.lower() in primary.lower() or stage.lower() in secondary.lower():
                matching.append(record)
                break
    return matching


def synthesize_stage_insight(
    anthropic_key: str, group_name: str, records: list[dict]
) -> str:
    """Synthesize a golden insight for a stage group (max 15 words)."""
    if not records:
        return "No insights available yet."

    # Build context from records (limit to 5 for faster response)
    insights = []
    for record in records[:5]:
        fields = record.get("fields", {})
        insight = fields.get("Key Insight") or ""
        influencer = fields.get("Influencer") or ""
        if insight:
            # Truncate long insights
            short_insight = insight[:150] + "..." if len(insight) > 150 else insight
            insights.append(f"- {influencer}: {short_insight}")

    if not insights:
        return "No insights available yet."

    try:
        client = anthropic.Anthropic(api_key=anthropic_key, timeout=30.0)

        prompt = f"""Given these insights about {group_name}:

{chr(10).join(insights)}

Write ONE actionable tip (max 12 words) as a direct instruction.
Start with a verb. Examples:
- "Ask about their timeline before discussing price."
- "Map all stakeholders before the first meeting."
- "Lead with a question, not a pitch."
Do NOT start with "Top performers" or similar. Just the action."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
    except anthropic.APITimeoutError:
        # Return a default insight on timeout
        return "Focus on understanding before persuading."
    except Exception as e:
        return f"Insight loading failed."


def generate_conversation_title(anthropic_key: str, first_message: str) -> str:
    """Generate a short conversation title from the first user message."""
    client = anthropic.Anthropic(api_key=anthropic_key, timeout=15.0)

    prompt = f"""Generate a 3-5 word title for this sales coaching conversation based on the user's question:

"{first_message}"

Return ONLY the title, no quotes or punctuation. Examples:
- Discovery Call Strategies
- Handling Price Objections
- Silent Prospect Follow-up
- Demo Engagement Tips"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def get_image_base64(image_path: Path) -> str:
    """Convert image to base64 for inline HTML."""
    if image_path.exists():
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def get_influencer_name(slug: str) -> str:
    """Get influencer name from slug."""
    if slug == "collective-wisdom":
        return "Collective Wisdom"
    for inf in INFLUENCERS:
        if inf["slug"] == slug:
            return inf["name"]
    return slug


def render_header():
    """Render header with title left, clickable avatar images on right."""
    # Initialize selected persona in session state
    if "selected_persona" not in st.session_state:
        st.session_state.selected_persona = None  # None = Collective Wisdom (all)

    # Sync from query params (on page load after click)
    params = st.query_params
    url_persona = params.get("persona", None)
    if url_persona == "":
        url_persona = None
    if url_persona != st.session_state.selected_persona:
        st.session_state.selected_persona = url_persona

    all_avatars = [COLLECTIVE_WISDOM] + INFLUENCERS  # 14 total

    # Build avatar HTML - images with onclick JavaScript
    avatar_html = ""
    for avatar in all_avatars:
        avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{avatar['slug']}.png"
        if not avatar_path.exists():
            continue

        b64 = get_image_base64(avatar_path)
        is_selected = (
            avatar["slug"] == "collective-wisdom"
            and st.session_state.selected_persona is None
        ) or st.session_state.selected_persona == avatar["slug"]

        # Styling
        border = "3px solid #4ECDC4" if is_selected else "2px solid #555"
        opacity = "1" if is_selected else "0.6"

        # JavaScript onclick - update query param
        if avatar["slug"] == "collective-wisdom":
            onclick = "window.location.search = ''"
        else:
            onclick = f"window.location.search = '?persona={avatar['slug']}'"

        avatar_html += f"""<img src="data:image/png;base64,{b64}"
            onclick="{onclick}"
            class="avatar-img"
            style="width:52px; height:52px; border-radius:50%;
                   border:{border}; opacity:{opacity}; cursor:pointer;
                   transition: all 0.15s ease;"
            title="{avatar['name']}">"""

    # Layout: title left, avatars right
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(
            """
        <div class="header-title">
            <h1>Sales Coach AI</h1>
            <p>Elite sales wisdom on demand</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
        <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-content:center; gap:8px 0; align-items:center; padding:12px 0;">
            {avatar_html}
        </div>
        """,
            unsafe_allow_html=True,
        )


def render_chat_interface(secrets: dict, records: list[dict]):
    """Render Claude.ai-style chat interface with conversation title and persona filtering."""
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_title" not in st.session_state:
        st.session_state.conversation_title = "New Conversation"

    # Filter records based on selected persona
    if st.session_state.get("selected_persona"):
        filtered_records = [
            r
            for r in records
            if st.session_state.selected_persona.lower()
            in (r.get("fields", {}).get("Influencer") or "").lower()
        ]
        persona_name = get_influencer_name(st.session_state.selected_persona)
        st.info(f"💬 Channeling **{persona_name}**'s coaching style")
    else:
        filtered_records = records

    # Display conversation title
    if st.session_state.messages:
        st.markdown(
            f'<div class="conversation-title">{st.session_state.conversation_title}</div>',
            unsafe_allow_html=True,
        )

    # Create a fixed-height container for chat messages
    chat_container = st.container(height=450)
    with chat_container:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("sources"):
                    with st.expander("📚 View sources", expanded=False):
                        for source in message["sources"]:
                            st.markdown(
                                f"**{source['influencer']}** ({source['stage']})"
                            )
                            if source.get("url"):
                                st.markdown(f"[View source]({source['url']})")

    # Chat input (outside container, stays at bottom)
    if prompt := st.chat_input("Describe your sales situation or ask a question..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Generate conversation title from first message
        if len(st.session_state.messages) == 1:
            try:
                st.session_state.conversation_title = generate_conversation_title(
                    secrets["anthropic_key"], prompt
                )
            except Exception:
                # Fallback: use first 5 words
                words = prompt.split()[:5]
                st.session_state.conversation_title = " ".join(words) + (
                    "..." if len(prompt.split()) > 5 else ""
                )

        # Find relevant records from filtered set
        relevant = find_relevant_records(filtered_records, prompt)

        if not relevant:
            if st.session_state.get("selected_persona"):
                persona_name = get_influencer_name(st.session_state.selected_persona)
                response = f"I couldn't find specific insights from {persona_name} matching your question. Try switching to 'Collective Wisdom' for broader advice, or ask about a different topic."
            else:
                response = "I couldn't find specific insights matching your question. Try rephrasing or asking about: discovery, objections, closing, negotiation, or prospecting."
            sources = []
        else:
            # Get advice with conversation context
            context = build_context(relevant)

            # Modify system prompt for persona if selected
            selected_persona = st.session_state.get("selected_persona")
            response = get_coaching_advice(
                secrets["anthropic_key"],
                prompt,
                context,
                st.session_state.messages[:-1],  # Exclude current message
                selected_persona,
            )
            sources = [
                {
                    "influencer": r.get("fields", {}).get("Influencer", "Unknown"),
                    "stage": r.get("fields", {}).get("Primary Stage", "General"),
                    "url": r.get("fields", {}).get("Source URL", ""),
                }
                for r in relevant
            ]

        # Add assistant response
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
                "sources": sources,
            }
        )

        st.rerun()

    # Clear chat button (subtle placement)
    if st.session_state.messages:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(
                "🗑️ Clear conversation", type="secondary", use_container_width=True
            ):
                st.session_state.messages = []
                st.session_state.conversation_title = "New Conversation"
                st.rerun()


def render_stages_sidebar(secrets: dict, records: list[dict]):
    """Render single-accordion stages sidebar with 1-line insights."""
    st.markdown("### Sales Stages")

    # Initialize session state
    if "stage_insights" not in st.session_state:
        st.session_state.stage_insights = {}
    if "expanded_group" not in st.session_state:
        st.session_state.expanded_group = None
    if "expanded_stage" not in st.session_state:
        st.session_state.expanded_stage = None

    # General Sales Mindset - always visible callout
    general_records = get_records_for_stage_group(records, ["General Sales Mindset"])
    if "General Sales Mindset" not in st.session_state.stage_insights:
        if general_records:
            with st.spinner("..."):
                st.session_state.stage_insights["General Sales Mindset"] = (
                    synthesize_stage_insight(
                        secrets["anthropic_key"],
                        "General Sales Mindset",
                        general_records,
                    )
                )
        else:
            st.session_state.stage_insights["General Sales Mindset"] = (
                "Serve, don't sell."
            )

    st.markdown(
        f"""
    <div class="mindset-callout">
        <strong>Mindset:</strong> {st.session_state.stage_insights['General Sales Mindset']}
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Stage groups - single accordion behavior
    for group_name, stages in STAGE_GROUPS.items():
        group_records = get_records_for_stage_group(records, stages)
        is_expanded = st.session_state.expanded_group == group_name

        # Group header button (no counter)
        icon = "▼" if is_expanded else "▶"
        if st.button(
            f"{icon} {group_name}",
            key=f"group_{group_name}",
            use_container_width=True,
            type="secondary",
        ):
            if is_expanded:
                st.session_state.expanded_group = None
                st.session_state.expanded_stage = None
            else:
                st.session_state.expanded_group = group_name
                st.session_state.expanded_stage = None
            st.rerun()

        # Show content if expanded
        if is_expanded:
            # Synthesize group insight if not cached
            if group_name not in st.session_state.stage_insights:
                if group_records:
                    with st.spinner("..."):
                        st.session_state.stage_insights[group_name] = (
                            synthesize_stage_insight(
                                secrets["anthropic_key"], group_name, group_records
                            )
                        )
                else:
                    st.session_state.stage_insights[group_name] = "No insights yet."

            # Show group insight ONLY if no stage is expanded (single insight display)
            if st.session_state.expanded_stage is None:
                st.markdown(
                    f'<div class="stage-insight">{st.session_state.stage_insights[group_name]}</div>',
                    unsafe_allow_html=True,
                )

            # Nested stages
            for stage in stages:
                stage_records = [
                    r
                    for r in records
                    if stage in (r.get("fields", {}).get("Primary Stage") or "")
                ]
                stage_expanded = st.session_state.expanded_stage == stage

                # Stage button (indented, no counter)
                stage_icon = "▼" if stage_expanded else "▶"
                col1, col2 = st.columns([0.1, 0.9])
                with col2:
                    if st.button(
                        f"{stage_icon} {stage}",
                        key=f"stage_{stage}",
                        use_container_width=True,
                        type="tertiary" if hasattr(st, "tertiary") else "secondary",
                    ):
                        if stage_expanded:
                            st.session_state.expanded_stage = None
                        else:
                            st.session_state.expanded_stage = stage
                        st.rerun()

                # Show stage insight if expanded (this is now the ONLY visible insight)
                if stage_expanded:
                    stage_key = f"stage_{stage}"
                    if stage_key not in st.session_state.stage_insights:
                        if stage_records:
                            with st.spinner("..."):
                                st.session_state.stage_insights[stage_key] = (
                                    synthesize_stage_insight(
                                        secrets["anthropic_key"], stage, stage_records
                                    )
                                )
                        else:
                            st.session_state.stage_insights[stage_key] = (
                                "No insights yet."
                            )

                    st.markdown(
                        f'<div class="stage-insight" style="padding-left: 2.5rem;">{st.session_state.stage_insights[stage_key]}</div>',
                        unsafe_allow_html=True,
                    )


def main():
    """Main app entry point."""
    # Get secrets
    secrets = get_secrets()

    if not all(
        [secrets["anthropic_key"], secrets["airtable_key"], secrets["airtable_base"]]
    ):
        st.error("Missing API credentials. Please configure secrets.")
        st.markdown(
            """
        **For Streamlit Cloud**: Add secrets in your app settings.

        **For local development**: Create a `.env` file with:
        ```
        ANTHROPIC_API_KEY=your_key
        AIRTABLE_API_KEY=your_key
        AIRTABLE_BASE_ID=your_base_id
        AIRTABLE_TABLE_NAME=Sales Wisdom
        ```
        """
        )
        return

    # Load records
    try:
        records = fetch_records(
            secrets["airtable_key"], secrets["airtable_base"], secrets["airtable_table"]
        )
    except Exception as e:
        st.error(f"Failed to load Airtable data: {e}")
        return

    # Render compact header with avatars
    render_header()

    st.markdown("---")

    # Two-column layout (wider chat area)
    chat_col, sidebar_col = st.columns([2.5, 1])

    with chat_col:
        render_chat_interface(secrets, records)

    with sidebar_col:
        render_stages_sidebar(secrets, records)

    # Minimal footer
    st.markdown("---")
    st.caption(
        f"Powered by Claude AI • {len(records)} insights from {len(INFLUENCERS)} experts"
    )


if __name__ == "__main__":
    main()
