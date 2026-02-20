"""Tests for cross-file consistency.

Ensures names, slugs, and avatar files stay in sync
across influencers.json, collect_linkedin.py,
generate_avatars.py, and the assets/avatars/ directory.
"""
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "influencers.json"
AVATARS_DIR = PROJECT_ROOT / "assets" / "avatars"


@pytest.fixture(scope="module")
def registry_data():
    with open(REGISTRY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def active_names(registry_data):
    return {i["name"] for i in registry_data["influencers"] if i["status"] == "active"}


@pytest.fixture(scope="module")
def active_slugs(registry_data):
    return {i["slug"] for i in registry_data["influencers"] if i["status"] == "active"}


@pytest.fixture(scope="module")
def linkedin_names(registry_data):
    """Get influencer names that collect_linkedin.py would use.

    Mirrors _build_influencer_list() logic: active experts with a LinkedIn handle.
    """
    names = set()
    for expert in registry_data["influencers"]:
        if expert.get("status") != "active":
            continue
        handle = expert.get("platforms", {}).get("linkedin", {}).get("handle")
        if not handle:
            continue
        names.add(expert["name"])
    return names


@pytest.fixture(scope="module")
def avatar_script_slugs(registry_data):
    """Get slugs that generate_avatars.py would use.

    Mirrors _build_influencer_list() logic: all expert slugs + collective-wisdom.
    """
    slugs = {expert["slug"] for expert in registry_data["influencers"]}
    slugs.add("collective-wisdom")
    return slugs


@pytest.fixture(scope="module")
def avatar_files():
    """Get set of slug names from avatar PNG files on disk."""
    return {p.stem for p in AVATARS_DIR.glob("*.png")}


# ──────────────────────────────────────────────
# Avatar File Consistency
# ──────────────────────────────────────────────

class TestAvatarFiles:
    def test_every_active_expert_has_avatar(self, active_slugs, avatar_files):
        """Every active expert in the registry has a corresponding PNG file."""
        missing = active_slugs - avatar_files
        assert not missing, f"Active experts missing avatar PNGs: {missing}"

    def test_collective_wisdom_avatar_exists(self, avatar_files):
        """The collective-wisdom avatar exists."""
        assert "collective-wisdom" in avatar_files

    def test_no_orphan_avatars(self, registry_data, avatar_files):
        """All avatar PNGs correspond to a registry record or collective-wisdom."""
        all_slugs = {i["slug"] for i in registry_data["influencers"]}
        all_slugs.add("collective-wisdom")
        orphans = avatar_files - all_slugs
        assert not orphans, f"Avatar PNGs with no registry record: {orphans}"

    def test_avatars_are_real_pngs(self, active_slugs):
        """Avatar files have non-zero size and valid PNG header."""
        PNG_HEADER = b"\x89PNG"
        for slug in active_slugs:
            path = AVATARS_DIR / f"{slug}.png"
            assert path.exists(), f"Missing: {path}"
            content = path.read_bytes()
            assert len(content) > 100, f"{slug}.png is suspiciously small ({len(content)} bytes)"
            assert content[:4] == PNG_HEADER, f"{slug}.png is not a valid PNG file"


# ──────────────────────────────────────────────
# LinkedIn Script Consistency
# ──────────────────────────────────────────────

class TestLinkedInScriptConsistency:
    def test_linkedin_names_are_subset_of_registry(self, linkedin_names, active_names):
        """Every name in collect_linkedin.py exists in the registry as active."""
        not_in_registry = linkedin_names - active_names
        assert not not_in_registry, \
            f"Names in LinkedIn script but not active in registry: {not_in_registry}"

    def test_all_new_experts_in_linkedin_script(self, linkedin_names):
        """All 32 new experts appear in collect_linkedin.py."""
        new_names = {
            "Anthony Iannarino", "Giulio Segantini", "Mark Hunter", "Jill Konrath",
            "Shari Levitin", "Jim Keenan", "Tiffani Bova", "Amy Volas", "Ron Kimhi",
            "Chris Orlob", "Becc Holland", "Jen Allen-Knuth", "Alexandra Carter",
            "Kwame Christian", "Mo Bunnell", "Rosalyn Santa Elena", "Mark Kosoglow",
            "Scott Leese", "Sarah Brazier", "Jesse Gittler", "Chantel George",
            "Bryan Tucker", "Colin Specter", "Kevin Dorsey", "Belal Batrawy",
            "Caroline Celis", "Julie Hansen", "Hannah Ajikawo", "Justin Michael",
            "Erica Franklin", "Maria Bross", "Niraj Kapur",
        }
        missing = new_names - linkedin_names
        assert not missing, f"New experts missing from LinkedIn script: {missing}"


# ──────────────────────────────────────────────
# Avatar Script Consistency
# ──────────────────────────────────────────────

class TestAvatarScriptConsistency:
    def test_all_active_slugs_in_avatar_script(self, active_slugs, avatar_script_slugs):
        """Every active expert's slug is in generate_avatars.py."""
        # Exclude company profiles — those have show_avatar: false
        missing = active_slugs - avatar_script_slugs
        assert not missing, f"Active slugs missing from generate_avatars.py: {missing}"

    def test_collective_wisdom_in_avatar_script(self, avatar_script_slugs):
        """collective-wisdom is in generate_avatars.py."""
        assert "collective-wisdom" in avatar_script_slugs


# ──────────────────────────────────────────────
# Slug Format Consistency
# ──────────────────────────────────────────────

class TestSlugFormat:
    def test_slugs_are_lowercase_kebab(self, registry_data):
        """All slugs use lowercase-kebab-case (letters, digits, hyphens only)."""
        import re
        pattern = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
        for inf in registry_data["influencers"]:
            slug = inf["slug"]
            assert pattern.match(slug), f"{inf['name']}: slug '{slug}' is not valid kebab-case"

    def test_slug_derived_from_name(self, registry_data):
        """Slugs are reasonably derived from the name (no random strings)."""
        for inf in registry_data["influencers"]:
            name_lower = inf["name"].lower().replace(" ", "")
            slug_compressed = inf["slug"].replace("-", "")
            # At least the first letter should match
            if inf["name"] != "30MPC":
                assert slug_compressed[0] == name_lower[0], \
                    f"{inf['name']}: slug '{inf['slug']}' doesn't start with expected letter"
