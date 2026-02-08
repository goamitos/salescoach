"""Tests for the persona system (data/personas.json + tools/personas.py).

Validates schema, confidence levels, framework counts, deal stage validity,
and system prompt construction.

Tests are organized into:
- TestPersonaSchema: validates the generated personas.json file
- TestPromptBuilder: validates the standalone prompt-building functions
- TestRAGHelpers: validates context prefix and top_n adjustment
"""
import json
from pathlib import Path

import pytest

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PERSONAS_PATH = PROJECT_ROOT / "data" / "personas.json"
INFLUENCERS_PATH = PROJECT_ROOT / "data" / "influencers.json"

# Import from tools (add to path so config.py resolves)
import sys
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from personas import (
    build_persona_system_prompt,
    build_persona_context_prefix,
    adjust_top_n,
    get_persona_info,
    validate_persona,
    CONFIDENCE_LABELS,
)
from config import DEAL_STAGES

# Valid deal stages for cross-reference
VALID_STAGES = set(DEAL_STAGES)

# Required fields in each persona entry
REQUIRED_PERSONA_FIELDS = {
    "slug", "name", "persona_version", "generated_at",
    "data_basis", "confidence", "voice_profile",
    "signature_frameworks", "signature_phrases",
    "key_topics", "deal_stage_strengths",
    "suggested_questions", "sample_response_pattern",
}

REQUIRED_VOICE_FIELDS = {
    "communication_style", "tone", "vocabulary_level",
    "sentence_structure", "teaching_approach",
}

REQUIRED_FRAMEWORK_FIELDS = {"name", "description"}


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def personas_data():
    """Load personas.json if it exists."""
    if not PERSONAS_PATH.exists():
        pytest.skip("data/personas.json not yet generated")
    with open(PERSONAS_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def personas(personas_data):
    return personas_data["personas"]


@pytest.fixture(scope="module")
def influencers():
    with open(INFLUENCERS_PATH) as f:
        data = json.load(f)
    return {i["slug"]: i for i in data["influencers"] if i["status"] == "active"}


@pytest.fixture
def sample_persona():
    """A minimal valid persona for prompt-builder tests."""
    return {
        "slug": "test-expert",
        "name": "Test Expert",
        "persona_version": 1,
        "generated_at": "2026-02-08T00:00:00",
        "data_basis": {
            "linkedin_posts": 0,
            "youtube_transcripts": 5,
            "total_insights": 25,
            "total_source_chars": 50000,
        },
        "confidence": "high",
        "voice_profile": {
            "communication_style": "Direct and practical",
            "tone": "Confident but approachable",
            "vocabulary_level": "Accessible with some technical terms",
            "sentence_structure": "Short declarative statements",
            "teaching_approach": "Anchors concepts in real-world examples",
        },
        "signature_frameworks": [
            {
                "name": "The SPIN Method",
                "description": "Situation, Problem, Implication, Need-payoff questioning",
                "typical_usage": "During discovery calls",
            },
            {
                "name": "Value Selling",
                "description": "Connecting features to business outcomes",
            },
        ],
        "signature_phrases": [
            "Sell the way buyers buy",
            "No one cares about your product",
        ],
        "key_topics": ["discovery", "value selling", "cold calling"],
        "deal_stage_strengths": ["Discovery", "Needs Analysis", "Initial Contact"],
        "suggested_questions": [
            "How do I handle a silent prospect during discovery?",
            "What's the best way to open a cold call?",
        ],
        "sample_response_pattern": "Test Expert typically starts with a story...",
    }


@pytest.fixture
def low_confidence_persona(sample_persona):
    """A low-confidence persona variant."""
    persona = sample_persona.copy()
    persona["confidence"] = "low"
    persona["data_basis"] = {
        "linkedin_posts": 0,
        "youtube_transcripts": 1,
        "total_insights": 3,
        "total_source_chars": 5000,
    }
    return persona


# ──────────────────────────────────────────────
# Schema Validation (requires generated file)
# ──────────────────────────────────────────────

class TestPersonaSchema:
    def test_valid_json_structure(self, personas_data):
        """Top-level structure has required keys."""
        assert "version" in personas_data
        assert "personas" in personas_data
        assert "total_personas" in personas_data
        assert isinstance(personas_data["personas"], list)

    def test_persona_count_matches(self, personas_data):
        """Reported count matches actual list length."""
        assert personas_data["total_personas"] == len(personas_data["personas"])

    def test_all_have_required_fields(self, personas):
        """Every persona has all required top-level fields."""
        for p in personas:
            missing = REQUIRED_PERSONA_FIELDS - set(p.keys())
            assert not missing, f"{p.get('name', '?')}: missing {missing}"

    def test_unique_slugs(self, personas):
        """All persona slugs are unique."""
        slugs = [p["slug"] for p in personas]
        assert len(slugs) == len(set(slugs))

    def test_valid_confidence_values(self, personas):
        """Confidence is one of high/medium/low."""
        for p in personas:
            assert p["confidence"] in ("high", "medium", "low"), \
                f"{p['name']}: invalid confidence '{p['confidence']}'"

    def test_voice_profile_fields(self, personas):
        """Every persona has all voice profile fields."""
        for p in personas:
            vp = p.get("voice_profile", {})
            missing = REQUIRED_VOICE_FIELDS - set(vp.keys())
            assert not missing, f"{p['name']}: missing voice fields {missing}"

    def test_voice_fields_are_nonempty_strings(self, personas):
        """Voice profile values are non-empty strings."""
        for p in personas:
            for field in REQUIRED_VOICE_FIELDS:
                value = p.get("voice_profile", {}).get(field, "")
                assert isinstance(value, str) and len(value) > 5, \
                    f"{p['name']}.voice_profile.{field}: too short or wrong type"

    def test_frameworks_have_required_fields(self, personas):
        """Each framework entry has name and description."""
        for p in personas:
            for fw in p.get("signature_frameworks", []):
                missing = REQUIRED_FRAMEWORK_FIELDS - set(fw.keys())
                assert not missing, \
                    f"{p['name']} framework: missing {missing}"

    def test_high_confidence_has_enough_frameworks(self, personas):
        """High-confidence personas have 2+ frameworks."""
        for p in personas:
            if p["confidence"] == "high":
                assert len(p.get("signature_frameworks", [])) >= 2, \
                    f"{p['name']}: high confidence but <2 frameworks"

    def test_deal_stage_strengths_are_valid(self, personas):
        """All deal_stage_strengths are from the valid DEAL_STAGES list."""
        for p in personas:
            for stage in p.get("deal_stage_strengths", []):
                assert stage in VALID_STAGES, \
                    f"{p['name']}: invalid stage '{stage}'"

    def test_suggested_questions_exist(self, personas):
        """Every persona has at least 2 suggested questions."""
        for p in personas:
            assert len(p.get("suggested_questions", [])) >= 2, \
                f"{p['name']}: needs at least 2 suggested questions"


class TestPersonaCoverage:
    def test_all_active_influencers_have_personas(self, personas, influencers):
        """Every active influencer should have a persona entry."""
        persona_slugs = {p["slug"] for p in personas}
        for slug in influencers:
            assert slug in persona_slugs, \
                f"Missing persona for active influencer: {slug}"

    def test_confidence_distribution(self, personas):
        """Confidence levels roughly match expected distribution."""
        counts = {"high": 0, "medium": 0, "low": 0}
        for p in personas:
            counts[p["confidence"]] += 1
        # At least some in each bucket (exact counts from PLAN.md: 18/13/15)
        assert counts["high"] > 0, "No high-confidence personas"
        assert counts["medium"] > 0, "No medium-confidence personas"


# ──────────────────────────────────────────────
# Prompt Builder (works without generated file)
# ──────────────────────────────────────────────

class TestPromptBuilder:
    def test_builds_prompt_with_all_sections(self, sample_persona):
        """System prompt contains all expected sections."""
        prompt = build_persona_system_prompt(
            sample_persona, "Some context records here"
        )
        assert "You are Test Expert" in prompt
        assert "== YOUR VOICE ==" in prompt
        assert "== YOUR FRAMEWORKS ==" in prompt
        assert "== YOUR SIGNATURE PHRASES ==" in prompt
        assert "== INSTRUCTIONS ==" in prompt
        assert "== YOUR KNOWLEDGE BASE ==" in prompt
        assert "Some context records here" in prompt

    def test_includes_voice_profile(self, sample_persona):
        """Voice profile fields appear in the prompt."""
        prompt = build_persona_system_prompt(sample_persona, "ctx")
        assert "Direct and practical" in prompt
        assert "Confident but approachable" in prompt

    def test_includes_frameworks(self, sample_persona):
        """Frameworks are listed in the prompt."""
        prompt = build_persona_system_prompt(sample_persona, "ctx")
        assert "The SPIN Method" in prompt
        assert "Value Selling" in prompt

    def test_includes_phrases(self, sample_persona):
        """Signature phrases appear as quoted text."""
        prompt = build_persona_system_prompt(sample_persona, "ctx")
        assert '"Sell the way buyers buy"' in prompt
        assert '"No one cares about your product"' in prompt

    def test_includes_instructions_with_name(self, sample_persona):
        """Instructions reference the expert by name."""
        prompt = build_persona_system_prompt(sample_persona, "ctx")
        assert "Respond AS Test Expert" in prompt

    def test_low_confidence_adds_modifier(self, low_confidence_persona):
        """Low-confidence personas get an honest-limitation note."""
        prompt = build_persona_system_prompt(low_confidence_persona, "ctx")
        assert "limited recorded teachings" in prompt
        assert "discovery" in prompt  # from key_topics

    def test_high_confidence_no_modifier(self, sample_persona):
        """High-confidence personas don't get the limitation note."""
        prompt = build_persona_system_prompt(sample_persona, "ctx")
        assert "limited recorded teachings" not in prompt

    def test_influencer_meta_adds_notes(self, sample_persona):
        """Registry metadata notes appear in the opening line."""
        meta = {"metadata": {"notes": "Former FBI negotiator"}}
        prompt = build_persona_system_prompt(sample_persona, "ctx", meta)
        assert "Former FBI negotiator" in prompt


# ──────────────────────────────────────────────
# RAG Helpers
# ──────────────────────────────────────────────

class TestRAGHelpers:
    def test_context_prefix_includes_frameworks(self, sample_persona):
        """Context prefix lists all frameworks."""
        prefix = build_persona_context_prefix(sample_persona)
        assert "The SPIN Method" in prefix
        assert "Value Selling" in prefix
        assert "Test Expert's Core Frameworks" in prefix

    def test_context_prefix_includes_topics(self, sample_persona):
        """Context prefix lists key topics."""
        prefix = build_persona_context_prefix(sample_persona)
        assert "discovery" in prefix
        assert "cold calling" in prefix

    def test_adjust_top_n_sparse_expert(self, low_confidence_persona):
        """Data-sparse experts get more records."""
        top_n = adjust_top_n(low_confidence_persona, total_records=5)
        assert top_n == 5  # min(5, 8)

    def test_adjust_top_n_rich_expert(self, sample_persona):
        """Data-rich experts keep default top_n."""
        top_n = adjust_top_n(sample_persona, total_records=40)
        assert top_n == 5  # default

    def test_adjust_top_n_respects_total(self):
        """top_n never exceeds total available records."""
        sparse = {"data_basis": {"total_insights": 3}}
        assert adjust_top_n(sparse, total_records=2) == 2


# ──────────────────────────────────────────────
# UI Helpers
# ──────────────────────────────────────────────

class TestUIHelpers:
    def test_get_persona_info_fields(self, sample_persona):
        """get_persona_info returns all expected UI fields."""
        info = get_persona_info(sample_persona)
        assert info["name"] == "Test Expert"
        assert info["confidence_label"] == "Deep Profile"
        assert info["total_insights"] == 25
        assert len(info["framework_names"]) == 2
        assert "The SPIN Method" in info["framework_names"]
        assert len(info["suggested_questions"]) == 2

    def test_confidence_labels_complete(self):
        """All confidence levels have labels."""
        for level in ("high", "medium", "low"):
            assert level in CONFIDENCE_LABELS

    def test_validate_persona_catches_missing_fields(self):
        """Validator catches missing required fields."""
        errors = validate_persona({"slug": "x", "name": "X"})
        assert any("Missing required field" in e for e in errors)

    def test_validate_persona_catches_invalid_stage(self):
        """Validator catches invalid deal stages."""
        persona = {
            "slug": "x", "name": "X", "confidence": "medium",
            "voice_profile": {}, "signature_frameworks": [],
            "signature_phrases": [], "key_topics": [],
            "deal_stage_strengths": ["Fake Stage"],
        }
        errors = validate_persona(persona)
        assert any("Invalid deal stage" in e for e in errors)

    def test_validate_persona_passes_for_valid(self, sample_persona):
        """Validator returns no errors for a valid persona."""
        errors = validate_persona(sample_persona)
        assert errors == []
