"""
Persona system prompt builder — standalone module.

Loads persona profiles from data/personas.json and builds
system prompts for expert persona mode. Designed to be imported
by any frontend (Streamlit, CLI, API) without coupling.

Usage:
    from personas import load_personas, build_persona_system_prompt

    personas = load_personas()
    persona = personas["chris-voss"]
    prompt = build_persona_system_prompt(persona, context_records)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config import DEAL_STAGES, PERSONAS_PATH, INFLUENCERS_PATH

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────

def load_personas(path: Path = PERSONAS_PATH) -> dict:
    """Load persona profiles keyed by slug.

    Returns:
        Dict mapping slug -> persona dict.
        Empty dict if file doesn't exist yet (pre-generation).
    """
    if not path.exists():
        logger.warning(f"Personas file not found: {path}")
        return {}
    with open(path) as f:
        data = json.load(f)
    return {p["slug"]: p for p in data.get("personas", [])}


def load_influencer_meta(path: Path = INFLUENCERS_PATH) -> dict:
    """Load influencer metadata keyed by slug.

    Returns:
        Dict mapping slug -> influencer dict from the registry.
    """
    if not path.exists():
        logger.warning(f"Influencers file not found: {path}")
        return {}
    with open(path) as f:
        data = json.load(f)
    return {i["slug"]: i for i in data.get("influencers", [])}


# ──────────────────────────────────────────────
# System Prompt Construction
# ──────────────────────────────────────────────

def build_persona_system_prompt(
    persona: dict,
    context: str,
    influencer_meta: dict | None = None,
) -> str:
    """Build a complete system prompt for persona mode.

    Args:
        persona: Single persona dict from personas.json.
        context: Pre-built context string from RAG records
                 (output of build_context() or equivalent).
        influencer_meta: Optional influencer registry entry for
                         supplementary info (notes, focus_areas).

    Returns:
        Full system prompt string ready for Claude API.
    """
    name = persona["name"]
    vp = persona.get("voice_profile", {})
    frameworks = persona.get("signature_frameworks", [])
    phrases = persona.get("signature_phrases", [])
    strengths = persona.get("deal_stage_strengths", [])
    confidence = persona.get("confidence", "medium")

    # Supplement with registry metadata if available
    notes = ""
    if influencer_meta:
        notes = influencer_meta.get("metadata", {}).get("notes", "")

    # Build sections
    voice_section = _build_voice_section(vp)
    framework_section = _build_framework_section(frameworks)
    phrase_section = _build_phrase_section(phrases)
    instructions = _build_instructions(name, strengths, vp.get("tone", ""))
    confidence_modifier = _build_confidence_modifier(confidence, persona)

    parts = [
        f"You are {name}, a renowned sales expert{f' known for {notes}' if notes else ''}.",
        "",
        "== YOUR VOICE ==",
        voice_section,
        "",
        "== YOUR FRAMEWORKS ==",
        framework_section,
        "",
        "== YOUR SIGNATURE PHRASES ==",
        phrase_section,
        "",
        "== INSTRUCTIONS ==",
        instructions,
    ]

    if confidence_modifier:
        parts.extend(["", confidence_modifier])

    parts.extend([
        "",
        "== YOUR KNOWLEDGE BASE ==",
        context,
    ])

    return "\n".join(parts)


def _build_voice_section(voice_profile: dict) -> str:
    """Format voice profile fields into prompt text."""
    fields = [
        ("Communication style", "communication_style"),
        ("Tone", "tone"),
        ("Vocabulary", "vocabulary_level"),
        ("Sentence structure", "sentence_structure"),
        ("Teaching approach", "teaching_approach"),
    ]
    lines = []
    for label, key in fields:
        value = voice_profile.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _build_framework_section(frameworks: list[dict]) -> str:
    """Format signature frameworks as a bullet list."""
    if not frameworks:
        return "(No specific frameworks documented)"
    lines = []
    for fw in frameworks:
        line = f"- {fw['name']}: {fw['description']}"
        if fw.get("typical_usage"):
            line += f" (Usage: {fw['typical_usage']})"
        lines.append(line)
    return "\n".join(lines)


def _build_phrase_section(phrases: list[str]) -> str:
    """Format signature phrases as quoted bullets."""
    if not phrases:
        return "(No signature phrases documented)"
    return "\n".join(f'- "{phrase}"' for phrase in phrases)


def _build_instructions(name: str, strengths: list[str], tone: str) -> str:
    """Build the behavioral instructions block."""
    strength_text = ", ".join(strengths) if strengths else "all deal stages"
    tone_text = tone if tone else "professional"

    return f"""1. Respond AS {name} in first person ("I", "my experience", "what I've found")
2. Ground every recommendation in YOUR specific frameworks and methodology
3. Reference your own real experiences and teachings
4. Use your characteristic phrases and terminology naturally
5. If outside your expertise ({strength_text}), acknowledge honestly
6. Do NOT reference other experts by name — you are speaking as yourself
7. Keep your characteristic {tone_text} tone throughout"""


def _build_confidence_modifier(confidence: str, persona: dict) -> str:
    """Add a modifier for low-confidence personas."""
    if confidence != "low":
        return ""
    topics = ", ".join(persona.get("key_topics", []))
    return f"""Note: You have limited recorded teachings on this specific topic.
Draw from your core principles ({topics}) and your general philosophy.
Be honest if asked about specific frameworks you haven't explicitly taught about."""


# ──────────────────────────────────────────────
# General Coach Prompt (unchanged from original)
# ──────────────────────────────────────────────

GENERAL_COACH_SYSTEM_PROMPT = """You are an expert sales coach who synthesizes wisdom from top sales leaders to provide actionable advice.

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


# ──────────────────────────────────────────────
# RAG Helpers
# ──────────────────────────────────────────────

def build_persona_context_prefix(persona: dict) -> str:
    """Build grounding context to prepend above individual RAG records.

    This gives the model awareness of the expert's full framework set
    even when only a few records are retrieved.
    """
    name = persona["name"]
    frameworks = persona.get("signature_frameworks", [])
    topics = persona.get("key_topics", [])

    parts = [f"# {name}'s Core Frameworks and Topics"]

    if frameworks:
        for fw in frameworks:
            parts.append(f"- **{fw['name']}**: {fw['description']}")

    if topics:
        parts.append(f"\nKey topics: {', '.join(topics)}")

    parts.append("\n# Specific Insights from Knowledge Base\n")
    return "\n".join(parts)


def adjust_top_n(persona: dict, total_records: int, default_top_n: int = 5) -> int:
    """Adjust top_n for RAG retrieval based on data density.

    Data-sparse experts get more records to compensate.
    Data-rich experts stick to the default, boosting quality over quantity.
    """
    total_insights = persona.get("data_basis", {}).get("total_insights", 0)

    if total_insights < 15:
        return min(total_records, 8)
    return default_top_n


# ──────────────────────────────────────────────
# UI Helpers
# ──────────────────────────────────────────────

CONFIDENCE_LABELS = {
    "high": "Deep Profile",
    "medium": "Standard",
    "low": "Limited",
}


def get_persona_info(persona: dict) -> dict:
    """Get UI-facing info for an expert persona.

    Returns:
        Dict with keys: name, confidence, confidence_label,
        total_insights, framework_names, suggested_questions.
    """
    confidence = persona.get("confidence", "medium")
    frameworks = persona.get("signature_frameworks", [])
    data_basis = persona.get("data_basis", {})

    return {
        "name": persona["name"],
        "slug": persona["slug"],
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LABELS.get(confidence, "Standard"),
        "total_insights": data_basis.get("total_insights", 0),
        "framework_names": [fw["name"] for fw in frameworks[:3]],
        "suggested_questions": persona.get("suggested_questions", []),
        "deal_stage_strengths": persona.get("deal_stage_strengths", []),
        "sample_response_pattern": persona.get("sample_response_pattern", ""),
    }


def validate_persona(persona: dict) -> list[str]:
    """Validate a single persona entry. Returns list of error strings."""
    errors = []
    required_fields = ["slug", "name", "confidence", "voice_profile",
                       "signature_frameworks", "signature_phrases",
                       "key_topics", "deal_stage_strengths"]

    for field in required_fields:
        if field not in persona:
            errors.append(f"Missing required field: {field}")

    # Validate confidence value
    if persona.get("confidence") not in ("high", "medium", "low"):
        errors.append(f"Invalid confidence: {persona.get('confidence')}")

    # Validate deal stages
    valid_stages = set(DEAL_STAGES)
    for stage in persona.get("deal_stage_strengths", []):
        if stage not in valid_stages:
            errors.append(f"Invalid deal stage: {stage}")

    # High-confidence should have 2+ frameworks
    if persona.get("confidence") == "high":
        if len(persona.get("signature_frameworks", [])) < 2:
            errors.append("High-confidence persona needs 2+ frameworks")

    return errors
