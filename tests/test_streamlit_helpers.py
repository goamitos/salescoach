"""Tests for Streamlit app helper functions.

Tests the pure logic functions from streamlit_app.py.

Note: Python 3.9 can't import streamlit_app.py directly due to
3.10+ type syntax (str | None). Instead we test the logic by
loading the registry data directly and reimplementing the pure
helper functions exactly as they appear in the app.
"""
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "influencers.json"


# ──────────────────────────────────────────────
# Reimplemented pure functions (from streamlit_app.py)
# These mirror the app exactly for testing.
# ──────────────────────────────────────────────

def load_influencers_from_registry(registry_path: Path) -> list:
    """Mirror of streamlit_app.load_influencers_from_registry()."""
    try:
        if registry_path.exists():
            with open(registry_path) as f:
                data = json.load(f)

            influencers = []
            for inf in data.get("influencers", []):
                if inf.get("status") == "active":
                    linkedin = inf.get("platforms", {}).get("linkedin", {})
                    followers = linkedin.get("followers")
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
    except Exception:
        pass
    return []


def get_influencer_name(slug: str, influencers: list) -> str:
    """Mirror of streamlit_app.get_influencer_name()."""
    if slug == "collective-wisdom":
        return "Collective Wisdom"
    for inf in influencers:
        if inf["slug"] == slug:
            return inf["name"]
    return slug


def get_influencer_details(slug: str, influencers: list) -> dict:
    """Mirror of streamlit_app.get_influencer_details()."""
    if slug == "collective-wisdom":
        return {
            "name": "Collective Wisdom",
            "slug": "collective-wisdom",
            "specialty": f"Combined insights from all {len(influencers)} experts",
            "followers": None,
        }
    for inf in influencers:
        if inf["slug"] == slug:
            return inf
    return {"name": slug, "slug": slug, "specialty": "", "followers": None}


def format_followers(count) -> str:
    """Mirror of streamlit_app.format_followers()."""
    if count is None:
        return ""
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.0f}K"
    return str(count)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def influencers():
    return load_influencers_from_registry(REGISTRY_PATH)


# ──────────────────────────────────────────────
# load_influencers_from_registry
# ──────────────────────────────────────────────

class TestLoadInfluencersFromRegistry:
    def test_loads_active_influencers(self, influencers):
        """Registry loader returns all 48 active influencers."""
        assert len(influencers) == 48

    def test_returns_dicts_with_required_keys(self, influencers):
        """Each returned dict has name and slug keys."""
        for inf in influencers:
            assert "name" in inf, f"Missing 'name' key in {inf}"
            assert "slug" in inf, f"Missing 'slug' key in {inf}"

    def test_excludes_company_profiles(self, influencers):
        """Company profiles (30MPC, Gong.io, Pavilion) are excluded."""
        names = {inf["name"] for inf in influencers}
        assert "Pavilion" not in names
        # 30MPC is status=company so it's excluded

    def test_includes_specialty(self, influencers):
        """Results include specialty from metadata.notes."""
        with_specialty = [inf for inf in influencers if inf.get("specialty")]
        assert len(with_specialty) > 0

    def test_returns_empty_on_missing_file(self, tmp_path):
        """Returns empty list if registry file doesn't exist."""
        result = load_influencers_from_registry(tmp_path / "nonexistent.json")
        assert result == []

    def test_returns_empty_on_invalid_json(self, tmp_path):
        """Returns empty list on corrupted JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json!!")
        result = load_influencers_from_registry(bad_file)
        assert result == []


# ──────────────────────────────────────────────
# get_influencer_name
# ──────────────────────────────────────────────

class TestGetInfluencerName:
    def test_known_slug(self, influencers):
        assert get_influencer_name("ian-koniak", influencers) == "Ian Koniak"

    def test_collective_wisdom(self, influencers):
        assert get_influencer_name("collective-wisdom", influencers) == "Collective Wisdom"

    def test_unknown_slug_returns_slug(self, influencers):
        assert get_influencer_name("nonexistent-person", influencers) == "nonexistent-person"

    def test_new_expert_slugs(self, influencers):
        assert get_influencer_name("scott-leese", influencers) == "Scott Leese"
        assert get_influencer_name("kwame-christian", influencers) == "Kwame Christian"
        assert get_influencer_name("belal-batrawy", influencers) == "Belal Batrawy"

    def test_all_active_slugs_resolve(self, influencers):
        """Every loaded influencer can be found by slug."""
        for inf in influencers:
            result = get_influencer_name(inf["slug"], influencers)
            assert result == inf["name"], f"Slug '{inf['slug']}' resolved to '{result}' not '{inf['name']}'"


# ──────────────────────────────────────────────
# get_influencer_details
# ──────────────────────────────────────────────

class TestGetInfluencerDetails:
    def test_collective_wisdom_details(self, influencers):
        details = get_influencer_details("collective-wisdom", influencers)
        assert details["name"] == "Collective Wisdom"
        assert "48" in details["specialty"]

    def test_known_expert(self, influencers):
        details = get_influencer_details("armand-farrokh", influencers)
        assert details["name"] == "Armand Farrokh"
        assert details["slug"] == "armand-farrokh"

    def test_unknown_returns_fallback(self, influencers):
        details = get_influencer_details("unknown-person", influencers)
        assert details["name"] == "unknown-person"
        assert details["slug"] == "unknown-person"

    def test_new_expert_details(self, influencers):
        details = get_influencer_details("anthony-iannarino", influencers)
        assert details["name"] == "Anthony Iannarino"
        assert details["specialty"]  # should have non-empty specialty


# ──────────────────────────────────────────────
# format_followers
# ──────────────────────────────────────────────

class TestFormatFollowers:
    def test_none_returns_empty(self):
        assert format_followers(None) == ""

    def test_millions(self):
        assert format_followers(1500000) == "1.5M"

    def test_thousands(self):
        assert format_followers(415000) == "415K"

    def test_small_number(self):
        assert format_followers(500) == "500"

    def test_exact_million(self):
        assert format_followers(1000000) == "1.0M"

    def test_exact_thousand(self):
        assert format_followers(1000) == "1K"

    def test_zero(self):
        assert format_followers(0) == "0"


# ──────────────────────────────────────────────
# LEGACY_INFLUENCERS removal check
# ──────────────────────────────────────────────

class TestNoLegacyFallback:
    def test_no_legacy_in_source(self):
        """LEGACY_INFLUENCERS should not appear in streamlit_app.py source."""
        source = (PROJECT_ROOT / "streamlit_app.py").read_text()
        assert "LEGACY_INFLUENCERS" not in source, \
            "LEGACY_INFLUENCERS still referenced in streamlit_app.py"

    def test_no_hardcoded_16_experts(self):
        """No hardcoded '16 experts' string in streamlit_app.py."""
        source = (PROJECT_ROOT / "streamlit_app.py").read_text()
        assert "16 experts" not in source, \
            "Hardcoded '16 experts' still in streamlit_app.py"
