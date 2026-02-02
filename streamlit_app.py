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

# Custom CSS - Executive Coaching Studio Theme with Auto Dark/Light Mode
st.markdown(
    """
<style>
/* Google Fonts - Distinctive typography */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

/* CSS Variables - Light mode (default) */
:root {
    --bg-primary: #faf9f7;
    --bg-secondary: #f0efed;
    --bg-card: #ffffff;
    --text-primary: #2d2d3a;
    --text-secondary: #6b6b7a;
    --accent: #2d2d3a;
    --accent-highlight: #D4A574;
    --accent-glow: rgba(212, 165, 116, 0.3);
    --border-subtle: rgba(0, 0, 0, 0.08);
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.08);
    --shadow-hover: 0 4px 16px rgba(0, 0, 0, 0.12);
    --user-msg-bg: linear-gradient(135deg, #2d2d3a 0%, #1a1a2e 100%);
    --user-msg-text: #ffffff;
    --assistant-msg-bg: #ffffff;
    --assistant-msg-border: #D4A574;
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-primary: #1a1a2e;
        --bg-secondary: #16162a;
        --bg-card: rgba(30, 30, 50, 0.7);
        --text-primary: #e8e8e8;
        --text-secondary: #a0a0a0;
        --accent: #D4A574;
        --accent-highlight: #D4A574;
        --accent-glow: rgba(212, 165, 116, 0.2);
        --border-subtle: rgba(255, 255, 255, 0.1);
        --shadow-card: 0 0 20px rgba(212, 165, 116, 0.1);
        --shadow-hover: 0 0 30px rgba(212, 165, 116, 0.15);
        --user-msg-bg: linear-gradient(135deg, #D4A574 0%, #c49464 100%);
        --user-msg-text: #1a1a2e;
        --assistant-msg-bg: rgba(30, 30, 50, 0.7);
        --assistant-msg-border: #D4A574;
    }
}

/* Global Streamlit overrides */
.stApp {
    background-color: var(--bg-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.stApp > header {
    background-color: transparent !important;
}

/* Remove default padding - reduced whitespace */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Fraunces', Georgia, serif !important;
    color: var(--text-primary) !important;
}

p, span, div, label {
    color: var(--text-primary);
}

/* Header styling - compact */
.header-container {
    text-align: center;
    padding: 0.5rem 0 0.25rem;
}

.header-title {
    margin-bottom: 0.75rem;
}

.header-title h1 {
    font-family: 'Fraunces', Georgia, serif !important;
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary) !important;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.01em;
}

/* Expert selector - CW left, 8x2 grid right */
.expert-selector {
    display: flex;
    justify-content: center;
    align-items: stretch;
    gap: 16px;
    padding: 0.5rem 0;
    margin: 0 auto;
}

/* Collective Wisdom - tall rectangular */
.cw-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.cw-avatar {
    width: 72px;
    height: 104px;
    border-radius: 12px;
    object-fit: cover;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 2px solid var(--border-subtle);
    opacity: 0.85;
}

.cw-avatar:hover {
    opacity: 1;
    box-shadow: 0 0 20px var(--accent-glow);
}

.cw-avatar.selected {
    opacity: 1;
    border: 3px solid var(--accent-highlight);
    box-shadow: 0 0 16px var(--accent-glow);
}

.cw-label {
    font-size: 0.7rem;
    text-align: center;
    margin-top: 0.35rem;
    color: var(--text-secondary);
    font-weight: 500;
}

/* Expert grid - 8 columns, 2 rows */
.experts-grid {
    display: grid;
    grid-template-columns: repeat(8, 48px);
    grid-template-rows: repeat(2, 48px);
    gap: 8px;
}

/* Individual expert avatars */
.avatar-img {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 2px solid var(--border-subtle);
    opacity: 0.7;
}

.avatar-img:hover {
    opacity: 1;
    transform: scale(1.1);
    box-shadow: 0 0 20px var(--accent-glow);
}

.avatar-img.selected {
    opacity: 1;
    border: 3px solid var(--accent-highlight);
    box-shadow: 0 0 16px var(--accent-glow);
}

/* Expert info panel */
.expert-info-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--accent-highlight);
    border-radius: 0 12px 12px 0;
    padding: 0.75rem 1rem;
    margin: 0.5rem auto;
    max-width: 600px;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: var(--shadow-card);
}

.expert-info-avatar {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--accent-highlight);
    flex-shrink: 0;
}

.expert-info-details {
    flex: 1;
}

.expert-info-name {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.25rem 0;
}

.expert-info-specialty {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 0.25rem 0;
    font-style: italic;
}

.expert-info-followers {
    font-size: 0.85rem;
    color: var(--accent-highlight);
    margin: 0;
    font-weight: 500;
}

.expert-info-badge {
    background: var(--accent-highlight);
    color: #1a1a2e;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}

/* Stage filter - compact dropdown style */
.stage-filter-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.5rem 0;
    margin-bottom: 0.5rem;
}

.stage-filter-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-weight: 500;
}

/* Suggested questions grid */
.suggestions-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-bottom: 1.5rem;
}

@media (max-width: 640px) {
    .suggestions-grid {
        grid-template-columns: 1fr;
    }
}

.suggestion-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    box-shadow: var(--shadow-card);
}

.suggestion-card:hover {
    border-color: var(--accent-highlight);
    box-shadow: var(--shadow-hover);
    transform: translateY(-2px);
}

.suggestion-card p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-primary);
    line-height: 1.4;
}

/* Chat messages */
.stChatMessage {
    border-radius: 12px !important;
    margin-bottom: 0.75rem !important;
    padding: 0.75rem 1rem !important;
}

[data-testid="stChatMessageContent"] {
    font-size: 0.875rem !important;
    line-height: 1.5 !important;
}

[data-testid="stChatMessageContent"] p {
    font-size: 0.875rem !important;
    margin-bottom: 0.5rem !important;
}

[data-testid="stChatMessageContent"] li {
    font-size: 0.875rem !important;
}

/* User messages */
.stChatMessage[data-testid="user-message"],
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: var(--user-msg-bg) !important;
    margin-left: 10% !important;
    border: none !important;
}

.stChatMessage[data-testid="user-message"] p,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p {
    color: var(--user-msg-text) !important;
}

/* Assistant messages */
.stChatMessage[data-testid="assistant-message"],
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: var(--assistant-msg-bg) !important;
    border-left: 3px solid var(--assistant-msg-border) !important;
    margin-right: 5% !important;
    box-shadow: var(--shadow-card);
}

/* Conversation title */
.conversation-title {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-subtle);
}

/* Chat input styling */
.stChatInput {
    border-color: var(--border-subtle) !important;
}

.stChatInput > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
}

.stChatInput textarea {
    color: var(--text-primary) !important;
}

/* Mindset callout */
.mindset-callout {
    background: var(--accent-glow);
    border-left: 4px solid var(--accent-highlight);
    padding: 1rem 1.25rem;
    border-radius: 0 12px 12px 0;
    margin: 1rem 0;
}

.mindset-callout strong {
    color: var(--accent-highlight);
    font-family: 'DM Sans', sans-serif;
}

.mindset-callout p {
    margin: 0;
    color: var(--text-primary);
}

/* Sources expander */
.stExpander {
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    background: var(--bg-secondary) !important;
}

.stExpander summary {
    color: var(--text-secondary) !important;
    font-size: 0.85rem;
}

/* Avatar selector buttons - minimal */
.stColumn .stButton > button {
    padding: 0.25rem 0.5rem !important;
    font-size: 0.65rem !important;
    border-radius: 8px !important;
    min-height: auto !important;
    background: transparent !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-secondary) !important;
}

.stColumn .stButton > button:hover {
    background: var(--accent-glow) !important;
    border-color: var(--accent-highlight) !important;
}

/* Regular buttons */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    padding: 0.75rem 1rem !important;
    text-align: left !important;
}

.stButton > button:hover {
    border-color: var(--accent-highlight) !important;
    transform: translateY(-1px);
    box-shadow: var(--shadow-hover);
}

.stButton > button[kind="secondary"] {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: var(--shadow-card);
}

.stButton > button[kind="primary"] {
    background: var(--accent-highlight) !important;
    color: #1a1a2e !important;
    border: 1px solid var(--accent-highlight) !important;
    font-weight: 600 !important;
}

/* Suggestion buttons specifically */
.welcome-container + div .stButton > button {
    min-height: 60px !important;
    font-size: 0.95rem !important;
}

/* Footer */
.footer-text {
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.85rem;
    padding: 1rem 0;
    border-top: 1px solid var(--border-subtle);
    margin-top: 2rem;
}

/* Horizontal dividers */
hr {
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: 1rem 0;
}

/* Hide default Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Responsive adjustments */
@media (max-width: 768px) {
    .header-title h1 {
        font-size: 1.75rem;
    }

    .expert-selector {
        flex-direction: column;
        gap: 12px;
        padding: 0.5rem 1rem;
    }

    .cw-avatar {
        width: 100px;
        height: 56px;
        border-radius: 10px;
    }

    .experts-grid {
        grid-template-columns: repeat(4, 40px);
        grid-template-rows: repeat(4, 40px);
        gap: 6px;
    }

    .avatar-img {
        width: 40px;
        height: 40px;
    }

    .expert-info-panel {
        flex-direction: column;
        text-align: center;
        padding: 1rem;
        margin: 0.5rem 1rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

# Constants
PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "influencers.json"

# Collective Wisdom avatar (displayed first, represents all experts)
COLLECTIVE_WISDOM = {"name": "Collective Wisdom", "slug": "collective-wisdom"}

# Legacy hardcoded influencer data (fallback)
LEGACY_INFLUENCERS = [
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


@st.cache_data(ttl=600)
def load_influencers_from_registry() -> list[dict]:
    """Load influencers from the registry JSON file.

    Returns list of dicts with name, slug, specialty, and followers for each influencer.
    Falls back to legacy list if registry is not available.
    """
    try:
        import json
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, "r") as f:
                data = json.load(f)

            influencers = []
            for inf in data.get("influencers", []):
                if inf.get("status") == "active":
                    # Get followers from LinkedIn platform
                    linkedin = inf.get("platforms", {}).get("linkedin", {})
                    followers = linkedin.get("followers")

                    # Get specialty from metadata.notes
                    metadata = inf.get("metadata", {})
                    specialty = metadata.get("notes", "")

                    influencers.append({
                        "name": inf["name"],
                        "slug": inf["slug"],
                        "specialty": specialty,
                        "followers": followers,
                    })

            if influencers:
                return influencers

    except Exception as e:
        st.warning(f"Could not load registry: {e}")

    return LEGACY_INFLUENCERS


# Dynamically load influencers (cached)
INFLUENCERS = load_influencers_from_registry()

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


def get_influencer_details(slug: str) -> dict:
    """Get full influencer details from slug."""
    if slug == "collective-wisdom":
        return {
            "name": "Collective Wisdom",
            "slug": "collective-wisdom",
            "specialty": "Combined insights from all 16 experts",
            "followers": None,
        }
    for inf in INFLUENCERS:
        if inf["slug"] == slug:
            return inf
    return {"name": slug, "slug": slug, "specialty": "", "followers": None}


def format_followers(count: int | None) -> str:
    """Format follower count for display."""
    if count is None:
        return ""
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.0f}K"
    return str(count)


def render_header():
    """Render centered header with title and expert selector using Streamlit buttons."""
    # Initialize selected persona in session state
    if "selected_persona" not in st.session_state:
        st.session_state.selected_persona = None  # None = Collective Wisdom (all)

    # Header title
    st.markdown(
        """
        <div class="header-container">
            <div class="header-title">
                <h1>Sales Coach AI</h1>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Expert selector using Streamlit columns and buttons
    all_experts = [{"name": "All Experts", "slug": None}] + INFLUENCERS

    # Create a row of image buttons
    # First row: CW + first 8 experts
    cols_row1 = st.columns([1.5] + [1] * 8)

    # CW button (larger)
    with cols_row1[0]:
        cw_path = PROJECT_ROOT / "assets" / "avatars" / "collective-wisdom.png"
        if cw_path.exists():
            cw_selected = st.session_state.selected_persona is None
            border_style = "3px solid #D4A574" if cw_selected else "2px solid rgba(255,255,255,0.1)"
            st.markdown(
                f"""<div style="text-align:center;">
                    <img src="data:image/png;base64,{get_image_base64(cw_path)}"
                        style="width:72px;height:104px;border-radius:12px;border:{border_style};cursor:pointer;object-fit:cover;">
                    <div style="font-size:0.7rem;color:#a0a0a0;margin-top:4px;">All Experts</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("All", key="select_cw", use_container_width=True):
                st.session_state.selected_persona = None
                st.rerun()

    # First 8 experts
    for i, inf in enumerate(INFLUENCERS[:8]):
        with cols_row1[i + 1]:
            avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{inf['slug']}.png"
            if avatar_path.exists():
                is_selected = st.session_state.selected_persona == inf["slug"]
                border_style = "3px solid #D4A574" if is_selected else "2px solid rgba(255,255,255,0.1)"
                st.markdown(
                    f"""<div style="text-align:center;">
                        <img src="data:image/png;base64,{get_image_base64(avatar_path)}"
                            style="width:48px;height:48px;border-radius:50%;border:{border_style};object-fit:cover;">
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(inf["name"].split()[0][:6], key=f"select_{inf['slug']}", use_container_width=True):
                    st.session_state.selected_persona = inf["slug"]
                    st.rerun()

    # Second row: remaining 8 experts (with spacer for CW column)
    if len(INFLUENCERS) > 8:
        cols_row2 = st.columns([1.5] + [1] * 8)
        with cols_row2[0]:
            st.write("")  # Spacer

        for i, inf in enumerate(INFLUENCERS[8:16]):
            with cols_row2[i + 1]:
                avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{inf['slug']}.png"
                if avatar_path.exists():
                    is_selected = st.session_state.selected_persona == inf["slug"]
                    border_style = "3px solid #D4A574" if is_selected else "2px solid rgba(255,255,255,0.1)"
                    st.markdown(
                        f"""<div style="text-align:center;">
                            <img src="data:image/png;base64,{get_image_base64(avatar_path)}"
                                style="width:48px;height:48px;border-radius:50%;border:{border_style};object-fit:cover;">
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button(inf["name"].split()[0][:6], key=f"select_{inf['slug']}", use_container_width=True):
                        st.session_state.selected_persona = inf["slug"]
                        st.rerun()

    # Show expert info panel when an individual expert is selected
    if st.session_state.selected_persona:
        details = get_influencer_details(st.session_state.selected_persona)
        avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{details['slug']}.png"
        avatar_b64 = get_image_base64(avatar_path) if avatar_path.exists() else ""

        followers_html = ""
        if details.get("followers"):
            followers_html = f'<p class="expert-info-followers">👥 {format_followers(details["followers"])} followers</p>'

        specialty_html = ""
        if details.get("specialty"):
            specialty_html = f'<p class="expert-info-specialty">"{details["specialty"]}"</p>'

        st.markdown(
            f"""
            <div class="expert-info-panel">
                <img src="data:image/png;base64,{avatar_b64}" class="expert-info-avatar">
                <div class="expert-info-details">
                    <p class="expert-info-name">{details['name']}</p>
                    {specialty_html}
                    {followers_html}
                </div>
                <span class="expert-info-badge">Selected ✓</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_stage_counts(records: list[dict]) -> dict:
    """Count records per stage group."""
    counts = {"All": len(records)}
    for group_name, stages in STAGE_GROUPS.items():
        group_records = get_records_for_stage_group(records, stages)
        counts[group_name] = len(group_records)
    # Count General Sales Mindset
    mindset_records = get_records_for_stage_group(records, ["General Sales Mindset"])
    counts["Mindset"] = len(mindset_records)
    return counts


def render_stage_tabs(records: list[dict]):
    """Render stage filter as a compact selectbox."""
    # Initialize selected stage in session state
    if "selected_stage_group" not in st.session_state:
        st.session_state.selected_stage_group = "All"

    counts = get_stage_counts(records)

    # Options with counts
    options = [
        f"All stages ({counts.get('All', 0)})",
        f"Planning & Research ({counts.get('Planning & Research', 0)})",
        f"Outreach & Contact ({counts.get('Outreach & Contact', 0)})",
        f"Discovery & Analysis ({counts.get('Discovery & Analysis', 0)})",
        f"Present & Prove Value ({counts.get('Present & Prove Value', 0)})",
        f"Close & Grow ({counts.get('Close & Grow', 0)})",
        f"Mindset ({counts.get('Mindset', 0)})",
    ]

    # Map display values to internal values
    value_map = {
        options[0]: "All",
        options[1]: "Planning & Research",
        options[2]: "Outreach & Contact",
        options[3]: "Discovery & Analysis",
        options[4]: "Present & Prove Value",
        options[5]: "Close & Grow",
        options[6]: "General Sales Mindset",
    }

    # Reverse map to get current display value
    reverse_map = {v: k for k, v in value_map.items()}
    current_display = reverse_map.get(st.session_state.selected_stage_group, options[0])

    # Centered layout with label
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        selected = st.selectbox(
            "Filter by deal stage:",
            options=options,
            index=options.index(current_display) if current_display in options else 0,
            key="stage_filter_select",
            label_visibility="collapsed",
        )

        # Update state if changed
        new_value = value_map.get(selected, "All")
        if new_value != st.session_state.selected_stage_group:
            st.session_state.selected_stage_group = new_value
            st.rerun()


def render_welcome_state():
    """Render the welcome/empty state with suggested questions - minimal, no headers."""
    # Suggested questions as Streamlit buttons in a 2x2 grid
    # No header needed - the chat input and cards are self-explanatory
    suggestions = [
        ("💰", "How do I handle price objections?"),
        ("👻", "My prospect went silent after the demo"),
        ("🎯", "Discovery questions for a CFO meeting"),
        ("⏰", "Creating urgency without being pushy"),
    ]

    # Add small vertical spacer
    st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    for i, (icon, question) in enumerate(suggestions):
        with col1 if i % 2 == 0 else col2:
            if st.button(
                f"{icon} {question}",
                key=f"suggestion_{i}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.prefill_question = question
                st.rerun()


def render_chat_interface(secrets: dict, records: list[dict]):
    """Render chat interface with conversation title, persona filtering, and stage filtering."""
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_title" not in st.session_state:
        st.session_state.conversation_title = "New Conversation"
    if "selected_stage_group" not in st.session_state:
        st.session_state.selected_stage_group = "All"

    # Filter records based on selected persona
    filtered_records = records
    if st.session_state.get("selected_persona"):
        filtered_records = [
            r
            for r in filtered_records
            if st.session_state.selected_persona.lower()
            in (r.get("fields", {}).get("Influencer") or "").lower()
        ]
        # Note: Expert info panel is now shown in header, no need to duplicate here

    # Filter records based on selected stage group
    stage_group = st.session_state.get("selected_stage_group", "All")
    if stage_group != "All":
        if stage_group == "General Sales Mindset":
            stages = ["General Sales Mindset"]
        else:
            stages = STAGE_GROUPS.get(stage_group, [])
        if stages:
            filtered_records = get_records_for_stage_group(filtered_records, stages)

    # Handle prefilled question from suggestion buttons
    prefill = st.session_state.pop("prefill_question", None)

    # Show welcome state if no messages
    if not st.session_state.messages and not prefill:
        render_welcome_state()
    elif prefill:
        # Process prefilled question immediately
        st.session_state.messages.append({"role": "user", "content": prefill})
        # Generate title
        try:
            st.session_state.conversation_title = generate_conversation_title(
                secrets["anthropic_key"], prefill
            )
        except Exception:
            words = prefill.split()[:5]
            st.session_state.conversation_title = " ".join(words) + "..."
        # Get response
        relevant = find_relevant_records(filtered_records, prefill)
        if relevant:
            context = build_context(relevant)
            response = get_coaching_advice(
                secrets["anthropic_key"],
                prefill,
                context,
                [],
                st.session_state.get("selected_persona"),
            )
            sources = [
                {
                    "influencer": r.get("fields", {}).get("Influencer", "Unknown"),
                    "stage": r.get("fields", {}).get("Primary Stage", "General"),
                    "url": r.get("fields", {}).get("Source URL", ""),
                }
                for r in relevant
            ]
        else:
            response = "I couldn't find specific insights matching your question."
            sources = []
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "sources": sources,
        })
        st.rerun()
    else:
        # Display conversation title
        st.markdown(
            f'<div class="conversation-title">{st.session_state.conversation_title}</div>',
            unsafe_allow_html=True,
        )

        # Chat messages container (flexible height)
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

    # Chat input
    if prompt := st.chat_input("Describe your sales situation or ask a question..."):
        # Add user message and display it immediately
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Show the user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Show loading indicator while processing
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
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
                        response = f"I couldn't find specific insights from {persona_name} matching your question. Try switching to 'All Experts' for broader advice, or ask about a different topic."
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


def render_mindset_callout(secrets: dict, records: list[dict]):
    """Render the always-visible mindset callout."""
    # Initialize session state
    if "stage_insights" not in st.session_state:
        st.session_state.stage_insights = {}

    # General Sales Mindset - always visible callout
    general_records = get_records_for_stage_group(records, ["General Sales Mindset"])
    if "General Sales Mindset" not in st.session_state.stage_insights:
        if general_records:
            with st.spinner("Loading mindset..."):
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
            <strong>💡 Mindset:</strong>
            <p>{st.session_state.stage_insights['General Sales Mindset']}</p>
        </div>
        """,
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

    # Render centered header with avatars
    render_header()

    # Only show stage filter when there's an active conversation
    has_conversation = bool(st.session_state.get("messages"))

    if has_conversation:
        # Render stage filter dropdown
        render_stage_tabs(records)

    # Chat interface (full width)
    render_chat_interface(secrets, records)

    # Minimal footer
    influencer_count = len(load_influencers_from_registry())
    st.markdown(
        f"""
        <div class="footer-text">
            Powered by Claude AI • {len(records)} insights from {influencer_count} experts
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
