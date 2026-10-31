"""Tests for the content-hash tag cache (Phase 0, WS3.2).

Covers:
- content_hash stability and change detection
- ensure_tag_cache_table idempotency
- needs_retag: new insight, changed content, schema bump, unchanged
- select_for_tagging: cap enforcement and deferred count
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from db import get_connection, init_db, upsert_insight
from tag_cache import (
    content_hash,
    ensure_tag_cache_table,
    needs_retag,
    record_tagged,
    seed_from_existing,
    select_for_tagging,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_insight(iid: str, key_insight: str = "Always ask open-ended questions") -> dict:
    """Return a minimal insight record for testing."""
    return {
        "id": iid,
        "influencer_slug": "test-expert",
        "influencer_name": "Test Expert",
        "source_type": "linkedin",
        "source_url": f"https://example.com/{iid}",
        "date_collected": "2026-01-01",
        "primary_stage": "Discovery",
        "secondary_stages": [],
        "key_insight": key_insight,
        "tactical_steps": ["Step 1", "Step 2"],
        "keywords": ["discovery", "questions"],
        "situation_examples": ["CFO meeting"],
        "best_quote": "Great quote",
        "relevance_score": 8,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Fresh test database initialized via init_db (runs all migrations)."""
    db_path = tmp_path / "test_tag_cache.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db: Path):
    """Open connection with tag_cache table ensured; closed after each test."""
    c = get_connection(db)
    ensure_tag_cache_table(c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_same_content_produces_same_hash(self) -> None:
        """content_hash must return the same value for identical insight dicts."""
        insight = _make_insight("hash-1")
        assert content_hash(insight) == content_hash(insight)

    def test_different_key_insight_produces_different_hash(self) -> None:
        """Changing key_insight must change the hash."""
        a = _make_insight("hash-2a", key_insight="Original insight")
        b = _make_insight("hash-2b", key_insight="Modified insight")
        assert content_hash(a) != content_hash(b)

    def test_hash_independent_of_non_tagging_fields(self) -> None:
        """Fields outside key_insight, tactical_steps, keywords do not affect hash."""
        a = _make_insight("hash-3a")
        b = dict(a)
        b["id"] = "hash-3b"
        b["influencer_name"] = "Completely Different Expert"
        b["best_quote"] = "Different quote entirely"
        b["relevance_score"] = 1
        assert content_hash(a) == content_hash(b)

    def test_none_fields_treated_as_empty_string(self) -> None:
        """An insight with None tactical_steps/keywords must hash the same as empty string."""
        a = _make_insight("hash-4a")
        a["tactical_steps"] = None
        a["keywords"] = None

        b = _make_insight("hash-4b")
        b["tactical_steps"] = None
        b["keywords"] = None

        assert content_hash(a) == content_hash(b)

    def test_two_insights_with_identical_relevant_fields_hash_equal(self) -> None:
        """Two different insights with the same key_insight/tactical_steps/keywords hash equal."""
        a = _make_insight("hash-5a")
        b = _make_insight("hash-5b")
        # Both use the same default key_insight, tactical_steps, and keywords
        assert content_hash(a) == content_hash(b)

    def test_hash_is_64_char_hex_string(self) -> None:
        """content_hash should return a 64-character hex string (SHA-256)."""
        h = content_hash(_make_insight("hash-6"))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_tactical_steps_list_field_hashed_stably(self) -> None:
        """List fields must produce a stable hash across separate calls."""
        insight = _make_insight("hash-7")
        insight["tactical_steps"] = ["alpha", "beta", "gamma"]
        h1 = content_hash(insight)
        h2 = content_hash(insight)
        assert h1 == h2

    def test_changed_tactical_steps_changes_hash(self) -> None:
        """Modifying tactical_steps must change the hash."""
        a = _make_insight("hash-8a")
        a["tactical_steps"] = ["Step A"]

        b = _make_insight("hash-8b")
        b["tactical_steps"] = ["Step B completely different"]

        assert content_hash(a) != content_hash(b)


# ---------------------------------------------------------------------------
# ensure_tag_cache_table
# ---------------------------------------------------------------------------


class TestEnsureTagCacheTable:
    def test_table_exists_after_call(self, conn: sqlite3.Connection) -> None:
        """tag_cache table must be present after ensure_tag_cache_table."""
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "tag_cache" in tables

    def test_idempotent_second_call(self, conn: sqlite3.Connection) -> None:
        """Calling ensure_tag_cache_table a second time must not raise."""
        ensure_tag_cache_table(conn)  # already called in fixture; call again
        ensure_tag_cache_table(conn)  # third time - still safe

    def test_expected_columns_present(self, conn: sqlite3.Connection) -> None:
        """tag_cache must have the four expected columns."""
        rows = conn.execute("PRAGMA table_info(tag_cache)").fetchall()
        col_names = {row[1] for row in rows}
        assert col_names >= {"insight_id", "content_hash", "schema_version", "tagged_at"}


# ---------------------------------------------------------------------------
# needs_retag
# ---------------------------------------------------------------------------


class TestNeedsRetag:
    def test_no_cache_row_returns_true(self, conn: sqlite3.Connection) -> None:
        """An insight with no cache row must need re-tagging."""
        insight = _make_insight("needs-1")
        assert needs_retag(conn, insight, current_schema_version=1) is True

    def test_cached_unchanged_same_version_returns_false(self, conn: sqlite3.Connection) -> None:
        """After recording, an unchanged insight at the same schema version must return False."""
        insight = _make_insight("needs-2")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=1)
        conn.commit()

        assert needs_retag(conn, insight, current_schema_version=1) is False

    def test_changed_content_returns_true(self, conn: sqlite3.Connection) -> None:
        """An insight whose content changed since last tagging must return True."""
        insight = _make_insight("needs-3", key_insight="Original insight content")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=1)
        conn.commit()

        changed_insight = dict(insight)
        changed_insight["key_insight"] = "Totally different insight content"
        assert needs_retag(conn, changed_insight, current_schema_version=1) is True

    def test_schema_bump_returns_true(self, conn: sqlite3.Connection) -> None:
        """A schema version bump must force re-tagging even if content is unchanged."""
        insight = _make_insight("needs-4")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=1)
        conn.commit()

        # current schema is now 2 -- must retag
        assert needs_retag(conn, insight, current_schema_version=2) is True

    def test_same_schema_version_no_change_returns_false(self, conn: sqlite3.Connection) -> None:
        """Identical hash and same schema version must return False (no retag needed)."""
        insight = _make_insight("needs-5")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=3)
        conn.commit()

        assert needs_retag(conn, insight, current_schema_version=3) is False

    def test_lower_stored_version_than_current_returns_true(self, conn: sqlite3.Connection) -> None:
        """If stored schema_version < current, must return True (schema bump)."""
        insight = _make_insight("needs-6")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=1)
        conn.commit()

        assert needs_retag(conn, insight, current_schema_version=5) is True


# ---------------------------------------------------------------------------
# record_tagged
# ---------------------------------------------------------------------------


class TestRecordTagged:
    def test_upsert_on_second_call(self, conn: sqlite3.Connection) -> None:
        """Calling record_tagged twice for the same insight must not raise (upsert)."""
        insight = _make_insight("record-1")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=1)
        conn.commit()

        # Second call with different values -- must update, not error
        record_tagged(conn, insight["id"], h, schema_version=2)
        conn.commit()

        row = conn.execute(
            "SELECT schema_version FROM tag_cache WHERE insight_id = ?",
            (insight["id"],),
        ).fetchone()
        assert row[0] == 2

    def test_stores_correct_values(self, conn: sqlite3.Connection) -> None:
        """record_tagged must persist the hash and schema version correctly."""
        insight = _make_insight("record-2")
        h = content_hash(insight)
        record_tagged(conn, insight["id"], h, schema_version=7)
        conn.commit()

        row = conn.execute(
            "SELECT content_hash, schema_version FROM tag_cache WHERE insight_id = ?",
            (insight["id"],),
        ).fetchone()
        assert row[0] == h
        assert row[1] == 7


# ---------------------------------------------------------------------------
# select_for_tagging
# ---------------------------------------------------------------------------


class TestSelectForTagging:
    def _seed_insights(self, conn: sqlite3.Connection, ids: list[str]) -> list[dict]:
        """Insert insight rows and return the insight dicts."""
        insights = []
        for iid in ids:
            rec = _make_insight(iid, key_insight=f"Unique insight text for {iid}")
            upsert_insight(conn, rec)
            insights.append(rec)
        conn.commit()
        return insights

    def test_all_untagged_returned_when_under_cap(self, conn: sqlite3.Connection) -> None:
        """All insights needing tagging are returned when max_items >= count."""
        insights = self._seed_insights(conn, ["sel-1", "sel-2", "sel-3"])
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=10)
        assert len(selected) == 3
        assert deferred == 0

    def test_cap_limits_returned_count(self, conn: sqlite3.Connection) -> None:
        """When max_items < insights needing tagging, exactly max_items are returned."""
        insights = self._seed_insights(conn, ["sel-4", "sel-5", "sel-6", "sel-7", "sel-8"])
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=3)
        assert len(selected) == 3

    def test_cap_produces_correct_deferred_count(self, conn: sqlite3.Connection) -> None:
        """deferred_count must equal total needing tagging minus max_items."""
        insights = self._seed_insights(conn, ["sel-9", "sel-10", "sel-11", "sel-12"])
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=2)
        assert len(selected) == 2
        assert deferred == 2

    def test_already_tagged_not_reselected(self, conn: sqlite3.Connection) -> None:
        """Insights already tagged with current hash and schema version are excluded."""
        insights = self._seed_insights(conn, ["sel-13", "sel-14", "sel-15"])

        # Pre-tag first insight so it should be skipped
        h = content_hash(insights[0])
        record_tagged(conn, insights[0]["id"], h, schema_version=1)
        conn.commit()

        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=10)
        selected_ids = {i["id"] for i in selected}
        assert insights[0]["id"] not in selected_ids
        assert len(selected) == 2
        assert deferred == 0

    def test_deferred_is_zero_when_all_fit(self, conn: sqlite3.Connection) -> None:
        """deferred_count is exactly 0 when all needing tagging fit within max_items."""
        insights = self._seed_insights(conn, ["sel-16", "sel-17"])
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=100)
        assert deferred == 0

    def test_empty_list_returns_empty_zero(self, conn: sqlite3.Connection) -> None:
        """Empty input list must return empty selected and deferred=0."""
        selected, deferred = select_for_tagging(conn, [], current_schema_version=1, max_items=10)
        assert selected == []
        assert deferred == 0

    def test_max_items_zero_returns_empty_with_all_deferred(self, conn: sqlite3.Connection) -> None:
        """max_items=0 means nothing is tagged; all needing tagging are deferred."""
        insights = self._seed_insights(conn, ["sel-18", "sel-19", "sel-20"])
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=1, max_items=0)
        assert selected == []
        assert deferred == 3

    def test_schema_bump_forces_retag_of_previously_tagged(self, conn: sqlite3.Connection) -> None:
        """After a schema bump, previously-tagged insights are re-selected."""
        insights = self._seed_insights(conn, ["sel-21", "sel-22"])

        # Tag both at schema_version=1
        for ins in insights:
            record_tagged(conn, ins["id"], content_hash(ins), schema_version=1)
        conn.commit()

        # Now run with schema_version=2 -- both should need re-tagging
        selected, deferred = select_for_tagging(conn, insights, current_schema_version=2, max_items=10)
        assert len(selected) == 2
        assert deferred == 0


# ---------------------------------------------------------------------------
# Per-tagger namespacing and seeding
# ---------------------------------------------------------------------------


class TestTaggerNamespace:
    def test_recording_under_one_tagger_does_not_cover_another(self, conn):
        insight = _make_insight("ns-1")
        record_tagged(conn, "ns-1", content_hash(insight), 1, tagger="methodology")
        assert needs_retag(conn, insight, 1, tagger="methodology") is False
        assert needs_retag(conn, insight, 1, tagger="audience") is True

    def test_two_taggers_keep_separate_rows(self, conn):
        insight = _make_insight("ns-2")
        record_tagged(conn, "ns-2", content_hash(insight), 1, tagger="methodology")
        record_tagged(conn, "ns-2", content_hash(insight), 3, tagger="audience")
        rows = conn.execute(
            "SELECT tagger, schema_version FROM tag_cache WHERE insight_id = ? ORDER BY tagger",
            ("ns-2",),
        ).fetchall()
        assert [tuple(r) for r in rows] == [("audience", 3), ("methodology", 1)]

    def test_default_tagger_is_its_own_namespace(self, conn):
        insight = _make_insight("ns-3")
        record_tagged(conn, "ns-3", content_hash(insight), 1)
        assert needs_retag(conn, insight, 1) is False
        assert needs_retag(conn, insight, 1, tagger="audience") is True


class TestSeedFromExisting:
    def test_seeded_insights_no_longer_need_tagging(self, conn):
        insights = [_make_insight(f"seed-{i}", key_insight=f"Insight {i}") for i in range(3)]
        assert seed_from_existing(conn, insights, 1, tagger="methodology") == 3
        selected, deferred = select_for_tagging(conn, insights, 1, max_items=10, tagger="methodology")
        assert selected == []
        assert deferred == 0

    def test_seeding_is_idempotent(self, conn):
        insights = [_make_insight("seed-x")]
        seed_from_existing(conn, insights, 1, tagger="audience")
        seed_from_existing(conn, insights, 1, tagger="audience")
        count = conn.execute("SELECT COUNT(*) FROM tag_cache").fetchone()[0]
        assert count == 1
