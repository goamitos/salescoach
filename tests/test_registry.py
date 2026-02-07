"""Tests for the influencer registry (data/influencers.json).

Validates schema, data integrity, and cross-file consistency
to catch drift between the registry and collection/UI scripts.
"""
import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "influencers.json"
AVATARS_DIR = PROJECT_ROOT / "assets" / "avatars"

# Required top-level fields for every influencer record
REQUIRED_FIELDS = {"id", "name", "slug", "status", "platforms", "metadata", "scores", "added_date", "last_scraped"}
REQUIRED_METADATA = {"focus_areas", "avatar_color", "notes"}
REQUIRED_SCORES = {"composite", "reach", "engagement", "frequency", "relevance", "originality"}
VALID_STATUSES = {"active", "company"}


@pytest.fixture(scope="module")
def registry():
    with open(REGISTRY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def influencers(registry):
    return registry["influencers"]


@pytest.fixture(scope="module")
def active_influencers(influencers):
    return [i for i in influencers if i["status"] == "active"]


@pytest.fixture(scope="module")
def company_influencers(influencers):
    return [i for i in influencers if i["status"] == "company"]


# ──────────────────────────────────────────────
# Registry Structure
# ──────────────────────────────────────────────

class TestRegistryStructure:
    def test_valid_json(self):
        """Registry file parses as valid JSON."""
        with open(REGISTRY_PATH) as f:
            data = json.load(f)
        assert "influencers" in data
        assert "version" in data

    def test_has_influencers(self, influencers):
        """Registry contains influencer records."""
        assert len(influencers) > 0

    def test_expected_counts(self, active_influencers, company_influencers):
        """Registry has expected active and company counts after expansion."""
        assert len(active_influencers) == 48
        assert len(company_influencers) == 3


# ──────────────────────────────────────────────
# Record Schema Validation
# ──────────────────────────────────────────────

class TestRecordSchema:
    def test_all_records_have_required_fields(self, influencers):
        """Every record has all required top-level fields."""
        for inf in influencers:
            missing = REQUIRED_FIELDS - set(inf.keys())
            assert not missing, f"{inf.get('name', 'unknown')}: missing fields {missing}"

    def test_all_records_have_valid_status(self, influencers):
        """Every record has a valid status value."""
        for inf in influencers:
            assert inf["status"] in VALID_STATUSES, f"{inf['name']}: invalid status '{inf['status']}'"

    def test_all_records_have_metadata(self, influencers):
        """Every record has required metadata fields."""
        for inf in influencers:
            metadata = inf.get("metadata", {})
            missing = REQUIRED_METADATA - set(metadata.keys())
            assert not missing, f"{inf['name']}: missing metadata {missing}"

    def test_all_records_have_scores(self, influencers):
        """Every record has required score fields."""
        for inf in influencers:
            scores = inf.get("scores", {})
            missing = REQUIRED_SCORES - set(scores.keys())
            assert not missing, f"{inf['name']}: missing scores {missing}"

    def test_scores_are_numeric(self, influencers):
        """All score values are numbers between 0 and 10."""
        for inf in influencers:
            for key, value in inf.get("scores", {}).items():
                assert isinstance(value, (int, float)), f"{inf['name']}.scores.{key}: not numeric"
                assert 0 <= value <= 10, f"{inf['name']}.scores.{key}: {value} not in [0, 10]"

    def test_focus_areas_is_list(self, influencers):
        """focus_areas is always a list of strings."""
        for inf in influencers:
            areas = inf.get("metadata", {}).get("focus_areas", [])
            assert isinstance(areas, list), f"{inf['name']}: focus_areas not a list"
            assert len(areas) > 0, f"{inf['name']}: focus_areas is empty"
            for area in areas:
                assert isinstance(area, str), f"{inf['name']}: focus_area item not a string"

    def test_avatar_color_is_hex(self, influencers):
        """avatar_color is a valid hex color string."""
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for inf in influencers:
            color = inf.get("metadata", {}).get("avatar_color", "")
            assert hex_pattern.match(color), f"{inf['name']}: invalid avatar_color '{color}'"


# ──────────────────────────────────────────────
# Uniqueness Constraints
# ──────────────────────────────────────────────

class TestUniqueness:
    def test_unique_ids(self, influencers):
        """All influencer IDs are unique."""
        ids = [i["id"] for i in influencers]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_unique_slugs(self, influencers):
        """All influencer slugs are unique."""
        slugs = [i["slug"] for i in influencers]
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {[x for x in slugs if slugs.count(x) > 1]}"

    def test_unique_names(self, influencers):
        """All influencer names are unique."""
        names = [i["name"] for i in influencers]
        assert len(names) == len(set(names)), f"Duplicate names: {[x for x in names if names.count(x) > 1]}"

    def test_id_matches_slug(self, influencers):
        """ID and slug are always identical."""
        for inf in influencers:
            assert inf["id"] == inf["slug"], f"{inf['name']}: id '{inf['id']}' != slug '{inf['slug']}'"


# ──────────────────────────────────────────────
# LinkedIn Platform Data
# ──────────────────────────────────────────────

class TestLinkedInData:
    def test_all_active_have_linkedin(self, active_influencers):
        """Every active influencer has a LinkedIn platform entry."""
        for inf in active_influencers:
            linkedin = inf.get("platforms", {}).get("linkedin")
            assert linkedin is not None, f"{inf['name']}: missing LinkedIn platform"

    def test_linkedin_has_handle(self, active_influencers):
        """Every active influencer's LinkedIn entry has a handle."""
        for inf in active_influencers:
            handle = inf.get("platforms", {}).get("linkedin", {}).get("handle")
            assert handle, f"{inf['name']}: missing LinkedIn handle"

    def test_linkedin_url_format(self, active_influencers):
        """LinkedIn URLs follow expected format."""
        for inf in active_influencers:
            url = inf.get("platforms", {}).get("linkedin", {}).get("url", "")
            assert url.startswith("https://www.linkedin.com/in/"), \
                f"{inf['name']}: unexpected LinkedIn URL format: {url}"


# ──────────────────────────────────────────────
# Specific New Expert Records
# ──────────────────────────────────────────────

NEW_EXPERT_NAMES = [
    "Anthony Iannarino", "Giulio Segantini", "Mark Hunter", "Jill Konrath",
    "Shari Levitin", "Jim Keenan", "Tiffani Bova", "Amy Volas", "Ron Kimhi",
    "Chris Orlob", "Becc Holland", "Jen Allen-Knuth", "Alexandra Carter",
    "Kwame Christian", "Mo Bunnell", "Rosalyn Santa Elena", "Mark Kosoglow",
    "Scott Leese", "Sarah Brazier", "Jesse Gittler", "Chantel George",
    "Bryan Tucker", "Colin Specter", "Kevin Dorsey", "Belal Batrawy",
    "Caroline Celis", "Julie Hansen", "Hannah Ajikawo", "Justin Michael",
    "Erica Franklin", "Maria Bross", "Niraj Kapur",
]


class TestNewExperts:
    def test_all_32_new_experts_present(self, influencers):
        """All 32 new experts from Monday CRM + Proposify are in the registry."""
        names = {i["name"] for i in influencers}
        for expert_name in NEW_EXPERT_NAMES:
            assert expert_name in names, f"Missing new expert: {expert_name}"

    def test_new_experts_are_active(self, influencers):
        """All 32 new experts have active status."""
        name_to_inf = {i["name"]: i for i in influencers}
        for expert_name in NEW_EXPERT_NAMES:
            inf = name_to_inf.get(expert_name)
            assert inf is not None, f"Missing: {expert_name}"
            assert inf["status"] == "active", f"{expert_name}: status is '{inf['status']}', expected 'active'"

    def test_new_experts_added_date(self, influencers):
        """All 32 new experts have the correct added_date."""
        name_to_inf = {i["name"]: i for i in influencers}
        for expert_name in NEW_EXPERT_NAMES:
            inf = name_to_inf[expert_name]
            assert inf["added_date"] == "2026-02-06", \
                f"{expert_name}: added_date is '{inf['added_date']}'"
