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

# Custom CSS - Refined Executive Coaching Theme
st.markdown(
    """
<style>
/* Google Fonts - Editorial typography */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Crimson+Pro:wght@400;500;600&display=swap');

/* CSS Variables */
:root {
    --bg-deep: #0f0f1a;
    --bg-card: rgba(25, 25, 40, 0.8);
    --bg-hover: rgba(212, 165, 116, 0.08);
    --text-primary: #f5f5f5;
    --text-secondary: #8a8a9a;
    --text-muted: #5a5a6a;
    --gold: #D4A574;
    --gold-dim: rgba(212, 165, 116, 0.6);
    --gold-glow: rgba(212, 165, 116, 0.15);
    --border: rgba(255, 255, 255, 0.06);
    --border-hover: rgba(212, 165, 116, 0.3);
}

/* Background with subtle gradient */
.stApp {
    background:
        radial-gradient(ellipse at 20% 0%, rgba(212, 165, 116, 0.03) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 100%, rgba(100, 100, 150, 0.03) 0%, transparent 50%),
        var(--bg-deep) !important;
    font-family: 'Crimson Pro', Georgia, serif !important;
    min-height: 100vh;
}

.stApp > header { background: transparent !important; }

/* Layout */
.block-container {
    padding: 0.75rem 1rem 2rem !important;
    max-width: 1000px !important;
}

/* Typography */
h1, h2, h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    color: var(--text-primary) !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em;
}

p, span, div, label, li {
    color: var(--text-primary);
    font-family: 'Crimson Pro', Georgia, serif;
}

/* Header */
.header-container {
    text-align: center;
    padding: 0.25rem 0;
    margin-bottom: 0.5rem;
}

.header-title h1 {
    font-size: 1.5rem !important;
    font-weight: 500 !important;
    color: var(--text-primary) !important;
    margin: 0;
    letter-spacing: 0.02em;
}

.header-subtitle {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    font-style: italic;
}

/* Expert Selector - Clean grid, no buttons */
.expert-selector {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
    padding: 0.75rem 0;
    margin: 0 auto;
}

.cw-avatar-wrap {
    position: relative;
    cursor: pointer;
    transition: transform 0.2s ease;
}

.cw-avatar-wrap:hover { transform: scale(1.02); }

.cw-avatar {
    width: 64px;
    height: 92px;
    border-radius: 10px;
    object-fit: cover;
    border: 2px solid var(--border);
    opacity: 0.75;
    transition: all 0.25s ease;
}

.cw-avatar:hover {
    opacity: 1;
    border-color: var(--gold-dim);
    box-shadow: 0 0 20px var(--gold-glow);
}

.cw-avatar.selected {
    opacity: 1;
    border-color: var(--gold);
    box-shadow: 0 0 24px var(--gold-glow), 0 0 0 1px var(--gold-dim);
}

.cw-label {
    position: absolute;
    bottom: -18px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.6rem;
    color: var(--text-muted);
    white-space: nowrap;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* Expert Grid - Scrollable horizontal strip */
.experts-grid {
    display: flex;
    flex-wrap: nowrap;
    gap: 6px;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 4px 8px 24px;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
    -webkit-overflow-scrolling: touch;
    max-width: 100%;
}

.experts-grid::-webkit-scrollbar {
    height: 4px;
}

.experts-grid::-webkit-scrollbar-track {
    background: transparent;
}

.experts-grid::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 2px;
}

.avatar-wrap {
    position: relative;
    cursor: pointer;
}

.avatar-img {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--border);
    opacity: 0.6;
    transition: all 0.2s ease;
    flex-shrink: 0;
}

.avatar-img:hover {
    opacity: 1;
    transform: scale(1.12);
    border-color: var(--gold-dim);
    box-shadow: 0 0 16px var(--gold-glow);
    z-index: 10;
}

.avatar-img.selected {
    opacity: 1;
    border-color: var(--gold);
    box-shadow: 0 0 20px var(--gold-glow);
}

/* Tooltip on hover */
.avatar-wrap .tooltip {
    position: absolute;
    bottom: -24px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-card);
    color: var(--text-primary);
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
    border: 1px solid var(--border);
    z-index: 100;
}

.avatar-wrap:hover .tooltip { opacity: 1; }

/* Expert Info Panel */
.expert-info-panel {
    background: var(--bg-card);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-left: 2px solid var(--gold);
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    margin: 0.75rem auto 0;
    max-width: 500px;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.expert-info-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--gold-dim);
}

.expert-info-details { flex: 1; }

.expert-info-name {
    font-family: 'Playfair Display', serif;
    font-size: 1rem;
    font-weight: 500;
    color: var(--text-primary);
    margin: 0;
}

.expert-info-specialty {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin: 2px 0;
    font-style: italic;
}

.expert-info-followers {
    font-size: 0.75rem;
    color: var(--gold);
    margin: 0;
}

.expert-info-badge {
    background: var(--gold);
    color: var(--bg-deep);
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

/* Suggestion Cards */
.suggestion-card {
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.9rem 1rem;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
}

.suggestion-card:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    transform: translateY(-1px);
}

.suggestion-card p {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-primary);
    line-height: 1.4;
}

/* Chat Messages */
.stChatMessage {
    border-radius: 8px !important;
    margin-bottom: 0.6rem !important;
    padding: 0.6rem 0.9rem !important;
}

[data-testid="stChatMessageContent"],
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li {
    font-size: 0.85rem !important;
    line-height: 1.55 !important;
    font-family: 'Crimson Pro', Georgia, serif !important;
}

[data-testid="stChatMessageContent"] p { margin-bottom: 0.4rem !important; }

/* User messages */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, var(--gold) 0%, #c49464 100%) !important;
    margin-left: 15% !important;
    border: none !important;
}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) span {
    color: var(--bg-deep) !important;
}

/* Assistant messages */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: var(--bg-card) !important;
    border-left: 2px solid var(--gold-dim) !important;
    margin-right: 10% !important;
}

/* Conversation title */
.conversation-title {
    font-family: 'Playfair Display', serif;
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}

/* Chat input */
.stChatInput > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

.stChatInput textarea {
    color: var(--text-primary) !important;
    font-family: 'Crimson Pro', serif !important;
}

/* Buttons */
.stButton > button {
    border-radius: 8px !important;
    font-family: 'Crimson Pro', serif !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    padding: 0.6rem 1rem !important;
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
}

.stButton > button:hover {
    background: var(--bg-hover) !important;
    border-color: var(--border-hover) !important;
}

/* Footer */
.footer-text {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
    padding: 1.5rem 0 0.5rem;
    letter-spacing: 0.03em;
}

/* Selectbox styling */
.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

.stSelectbox label { color: var(--text-secondary) !important; }

/* Expander */
.stExpander {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    background: transparent !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }

/* Avatar select buttons - minimal styling for header area */
/* Target only the avatar section buttons, not suggestion cards */
[data-testid="stHorizontalBlock"] .stColumn .stButton > button {
    font-size: 0.6rem !important;
    padding: 2px 4px !important;
    margin-top: 2px !important;
    background: transparent !important;
    border: none !important;
    color: var(--text-muted) !important;
    opacity: 0.5;
    transition: all 0.2s ease !important;
    height: auto !important;
    min-height: 0 !important;
}

[data-testid="stHorizontalBlock"] .stColumn .stButton > button:hover {
    color: var(--gold) !important;
    opacity: 0.9;
}

/* Suggestion card buttons - keep them styled properly */
button[kind="secondary"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    font-family: 'Crimson Pro', serif !important;
    font-size: 0.9rem !important;
    padding: 0.9rem 1rem !important;
    opacity: 1 !important;
    text-align: left !important;
}

button[kind="secondary"]:hover {
    background: var(--bg-hover) !important;
    border-color: var(--border-hover) !important;
    transform: translateY(-1px);
}

/* Responsive */
@media (max-width: 768px) {
    .block-container {
        padding: 0.5rem 0.75rem !important;
    }

    .experts-grid {
        gap: 4px;
        padding: 4px 4px 20px;
    }

    .avatar-img {
        width: 36px;
        height: 36px;
    }

    .cw-avatar {
        width: 56px;
        height: 80px;
    }

    .expert-selector {
        flex-direction: column;
        gap: 16px;
    }

    .expert-info-panel {
        flex-direction: column;
        text-align: center;
        padding: 1rem;
        margin: 0.5rem 1rem;
    }

    .stColumn .stButton > button {
        font-size: 0.6rem !important;
        padding: 1px 4px !important;
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


@st.cache_data(ttl=600)
def load_influencers_from_registry() -> list[dict]:
    """Load influencers from the registry JSON file.

    Returns list of dicts with name, slug, specialty, and followers for each active influencer.
    The registry (data/influencers.json) is the sole source of truth.
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

    return []


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


def get_secrets() -> dict[str, str | None]:
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
def fetch_records(_airtable_key: str, _base_id: str, _table_name: str) -> list[dict[str, any]]:
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


def build_context(records: list[dict[str, any]]) -> str:
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


def get_records_for_stage_group(records: list[dict[str, any]], stages: list[str]) -> list[dict[str, any]]:
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
    anthropic_key: str, group_name: str, records: list[dict[str, any]]
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
    """Convert image to base64 for inline HTML, with session state caching."""
    # Initialize cache in session state if not present
    if "avatar_base64_cache" not in st.session_state:
        st.session_state.avatar_base64_cache = {}

    cache_key = str(image_path)

    # Return cached value if available
    if cache_key in st.session_state.avatar_base64_cache:
        return st.session_state.avatar_base64_cache[cache_key]

    # Encode and cache
    if image_path.exists():
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            st.session_state.avatar_base64_cache[cache_key] = encoded
            return encoded
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
            "specialty": f"Combined insights from all {len(INFLUENCERS)} experts",
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


def render_header() -> None:
    """Render header with title and scrollable expert selector."""
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

    # Build HTML for scrollable avatar strip
    # CW avatar first, then all experts in a horizontal scroll
    cw_path = PROJECT_ROOT / "assets" / "avatars" / "collective-wisdom.png"
    cw_selected = "selected" if st.session_state.selected_persona is None else ""
    cw_b64 = get_image_base64(cw_path) if cw_path.exists() else ""

    avatar_html_parts = []

    # Collective Wisdom (larger, first)
    avatar_html_parts.append(
        f'<div class="cw-avatar-wrap">'
        f'<img src="data:image/png;base64,{cw_b64}" class="cw-avatar {cw_selected}">'
        f'<span class="cw-label">All</span>'
        f'</div>'
    )

    # All expert avatars
    for inf in INFLUENCERS:
        avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{inf['slug']}.png"
        if not avatar_path.exists():
            continue
        b64 = get_image_base64(avatar_path)
        is_selected = "selected" if st.session_state.selected_persona == inf["slug"] else ""
        first_name = inf["name"].split()[0]
        avatar_html_parts.append(
            f'<div class="avatar-wrap">'
            f'<img src="data:image/png;base64,{b64}" class="avatar-img {is_selected}" title="{inf["name"]}">'
            f'<span class="tooltip">{inf["name"]}</span>'
            f'</div>'
        )

    # Render the scrollable container
    st.markdown(
        f'<div class="expert-selector"><div class="experts-grid">{"".join(avatar_html_parts)}</div></div>',
        unsafe_allow_html=True,
    )

    # Hidden selection buttons (Streamlit needs real buttons for state changes)
    # Use compact columns - batch them in groups to reduce visual footprint
    BATCH_SIZE = 12
    all_items = [COLLECTIVE_WISDOM] + INFLUENCERS

    for batch_start in range(0, len(all_items), BATCH_SIZE):
        batch = all_items[batch_start:batch_start + BATCH_SIZE]
        cols = st.columns(len(batch))
        for i, item in enumerate(batch):
            with cols[i]:
                slug = item.get("slug")
                is_cw = slug == "collective-wisdom"
                key = "select_cw" if is_cw else f"select_{slug}"
                label = "All" if is_cw else item["name"].split()[0][:5]
                if st.button(label, key=key, use_container_width=True):
                    st.session_state.selected_persona = None if is_cw else slug
                    st.rerun()

    # Show expert info panel when an individual expert is selected
    if st.session_state.selected_persona:
        details = get_influencer_details(st.session_state.selected_persona)
        avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{details['slug']}.png"
        avatar_b64 = get_image_base64(avatar_path) if avatar_path.exists() else ""

        followers_html = ""
        if details.get("followers"):
            followers_html = f'<p class="expert-info-followers">{format_followers(details["followers"])} followers</p>'

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
                <span class="expert-info-badge">Selected</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_stage_counts(records: list[dict[str, any]]) -> dict[str, int]:
    """Count records per stage group."""
    counts = {"All": len(records)}
    for group_name, stages in STAGE_GROUPS.items():
        group_records = get_records_for_stage_group(records, stages)
        counts[group_name] = len(group_records)
    # Count General Sales Mindset
    mindset_records = get_records_for_stage_group(records, ["General Sales Mindset"])
    counts["Mindset"] = len(mindset_records)
    return counts


def render_stage_tabs(records: list[dict[str, any]]) -> None:
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


def render_welcome_state() -> None:
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


def render_chat_interface(secrets: dict[str, str | None], records: list[dict[str, any]]) -> None:
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
        # Get the actual influencer name from the slug for exact matching
        persona_name = get_influencer_name(st.session_state.selected_persona)
        filtered_records = [
            r
            for r in filtered_records
            if (r.get("fields", {}).get("Influencer") or "").lower() == persona_name.lower()
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


def render_mindset_callout(secrets: dict[str, str | None], records: list[dict[str, any]]) -> None:
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


def main() -> None:
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
