"""Claude API calls for coaching, persona mode, and title generation."""
from __future__ import annotations

from typing import Optional

import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-20250514"


def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from secrets or env."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("ANTHROPIC_API_KEY")


def get_coaching_advice(
    scenario: str,
    context: str,
    chat_history: list[dict],
    persona: Optional[dict] = None,
) -> str:
    """Call Claude to synthesize coaching advice.

    Args:
        scenario: The user's question/situation
        context: Built context string from relevant insights
        chat_history: Prior messages for conversation continuity
        persona: Optional persona dict from personas.json for expert mode
    """
    api_key = get_anthropic_key()
    if not api_key:
        return "API key not configured. Please add ANTHROPIC_API_KEY to secrets."

    client = anthropic.Anthropic(api_key=api_key)

    if persona:
        system_prompt = _build_persona_prompt(persona)
    else:
        system_prompt = _build_general_prompt()

    # Build messages with chat history for context
    messages = []
    history_to_include = chat_history[-6:] if len(chat_history) > 6 else chat_history
    for msg in history_to_include:
        messages.append({"role": msg["role"], "content": msg["content"]})

    user_prompt = f"""A salesperson asks:

"{scenario}"

Based on these expert insights from top sales leaders:

{context}

Provide specific, actionable coaching advice. Reference which expert's wisdom you're drawing from when relevant."""

    messages.append({"role": "user", "content": user_prompt})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _build_general_prompt() -> str:
    """Standard coach system prompt."""
    return """You are an expert sales coach who synthesizes wisdom from top sales leaders to provide actionable advice.

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


def _build_persona_prompt(persona: dict) -> str:
    """Build a rich persona-mode system prompt from persona data."""
    name = persona.get("name", "Expert")
    voice = persona.get("voice_profile", {})
    frameworks = persona.get("signature_frameworks", [])
    phrases = persona.get("signature_phrases", [])
    key_topics = persona.get("key_topics", [])
    strengths = persona.get("deal_stage_strengths", [])
    confidence = persona.get("confidence", "medium")

    prompt = f"""You are {name}, a renowned sales expert.

== YOUR VOICE ==
{voice.get('communication_style', '')}
{voice.get('tone', '')}
{voice.get('teaching_approach', '')}

== YOUR FRAMEWORKS =="""

    for fw in frameworks[:5]:
        prompt += f"\n- {fw['name']}: {fw.get('description', '')}"

    if phrases:
        prompt += "\n\n== YOUR SIGNATURE PHRASES =="
        for phrase in phrases[:5]:
            prompt += f'\n- "{phrase}"'

    prompt += f"""

== INSTRUCTIONS ==
1. Respond AS {name} in first person ("I", "my experience", "what I've found")
2. Ground every recommendation in YOUR specific frameworks and methodology
3. Reference your own real experiences and teachings
4. Use your characteristic phrases and terminology naturally
5. If outside your expertise ({', '.join(strengths[:3])}), acknowledge honestly
6. Do NOT reference other experts by name -- you are speaking as yourself
7. Keep your characteristic {voice.get('tone', 'professional')} tone throughout"""

    if confidence == "low":
        prompt += f"""

Note: You have limited recorded teachings on this specific topic.
Draw from your core principles ({', '.join(key_topics[:3])}) and your general philosophy.
Be honest if asked about specific frameworks you haven't explicitly taught about."""

    prompt += """

== YOUR KNOWLEDGE BASE ==
The insights below are from your own teachings and content:"""

    return prompt


def generate_conversation_title(first_message: str) -> str:
    """Generate a short conversation title from the first user message."""
    api_key = get_anthropic_key()
    if not api_key:
        words = first_message.split()[:5]
        return " ".join(words) + "..."

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=15.0)
        prompt = f"""Generate a 3-5 word title for this sales coaching conversation:

"{first_message}"

Return ONLY the title, no quotes or punctuation. Examples:
- Discovery Call Strategies
- Handling Price Objections
- Silent Prospect Follow-up"""

        response = client.messages.create(
            model=MODEL,
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        words = first_message.split()[:5]
        return " ".join(words) + ("..." if len(first_message.split()) > 5 else "")


def synthesize_stage_insight(group_name: str, insights: list[dict]) -> str:
    """Synthesize a golden insight for a stage group (max 12 words)."""
    if not insights:
        return "No insights available yet."

    short_insights = []
    for insight in insights[:5]:
        key = insight.get("key_insight", "")
        name = insight.get("influencer_name", "")
        if key:
            short = key[:150] + "..." if len(key) > 150 else key
            short_insights.append(f"- {name}: {short}")

    if not short_insights:
        return "No insights available yet."

    api_key = get_anthropic_key()
    if not api_key:
        return "Focus on understanding before persuading."

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        prompt = f"""Given these insights about {group_name}:

{chr(10).join(short_insights)}

Write ONE actionable tip (max 12 words) as a direct instruction.
Start with a verb. Do NOT start with "Top performers" or similar. Just the action."""

        response = client.messages.create(
            model=MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except anthropic.APITimeoutError:
        return "Focus on understanding before persuading."
    except Exception:
        return "Insight loading failed."
