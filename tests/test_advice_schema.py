"""Tests for the advice-library schema migration (Phase 0, WS3.1).

Covers:
- New columns present after init_db
- schema version set correctly
- idempotency of migrate_advice_columns
- column defaults for source_class and curated
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from db import get_connection, init_db, upsert_insight
from advice_schema import (
    ADVICE_SCHEMA_VERSION,
    GAP_TYPES,
    get_schema_version,
    migrate_advice_columns,
    set_schema_version,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_EXPECTED_NEW_COLUMNS = {
    "gap_type",
    "source_class",
    "curated",
    "last_seen",
    "applicability",
}


def _make_minimal_insight(iid: str) -> dict:
    """Return a minimal insight record for testing inserts."""
    return {
        "id": iid,
        "influencer_slug": "test-expert",
        "influencer_name": "Test Expert",
        "source_type": "linkedin",
        "source_url": f"https://example.com/{iid}",
        "date_collected": "2026-01-01",
        "primary_stage": "Discovery",
        "secondary_stages": [],
        "key_insight": "Always ask open-ended questions",
        "tactical_steps": ["Step 1"],
        "keywords": ["discovery"],
        "situation_examples": ["CFO meeting"],
        "best_quote": "Great quote here",
        "relevance_score": 8,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Fresh test database initialized via init_db (which runs all migrations)."""
    db_path = tmp_path / "test_advice.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db: Path):
    """Open connection to the test database; closed after each test."""
    c = get_connection(db)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Column presence
# ---------------------------------------------------------------------------

class TestNewColumnsPresent:
    def test_all_five_columns_exist_after_init_db(self, conn: sqlite3.Connection) -> None:
        """All five new advice-schema columns must appear in the insights table."""
        rows = conn.execute("PRAGMA table_info(insights)").fetchall()
        col_names = {row["name"] for row in rows}
        for col in _EXPECTED_NEW_COLUMNS:
            assert col in col_names, f"Column missing: {col}"


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_schema_version_equals_constant_after_migration(self, conn: sqlite3.Connection) -> None:
        """PRAGMA user_version must equal ADVICE_SCHEMA_VERSION after init_db."""
        assert get_schema_version(conn) == ADVICE_SCHEMA_VERSION

    def test_set_schema_version_round_trips(self, conn: sqlite3.Connection) -> None:
        """set_schema_version writes a value that get_schema_version reads back."""
        set_schema_version(conn, 42)
        assert get_schema_version(conn) == 42
        # Restore so other tests are unaffected
        set_schema_version(conn, ADVICE_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_call_does_not_raise(self, db: Path) -> None:
        """Calling migrate_advice_columns twice must not raise an error."""
        migrate_advice_columns(db)  # first call (already ran in init_db)
        migrate_advice_columns(db)  # second call, must be safe

    def test_second_call_leaves_columns_unchanged(self, db: Path) -> None:
        """Column count must be the same before and after a second migration call."""
        conn = get_connection(db)
        before = {row["name"] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
        conn.close()

        migrate_advice_columns(db)

        conn = get_connection(db)
        after = {row["name"] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
        conn.close()

        assert before == after

    def test_second_call_leaves_version_unchanged(self, db: Path) -> None:
        """Schema version must remain at ADVICE_SCHEMA_VERSION after second call."""
        migrate_advice_columns(db)
        conn = get_connection(db)
        version = get_schema_version(conn)
        conn.close()
        assert version == ADVICE_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Column defaults
# ---------------------------------------------------------------------------

class TestColumnDefaults:
    def test_source_class_default_is_external(self, conn: sqlite3.Connection) -> None:
        """A freshly inserted row must have source_class = 'external'."""
        upsert_insight(conn, _make_minimal_insight("default-test-1"))
        conn.commit()
        row = conn.execute(
            "SELECT source_class FROM insights WHERE id = ?", ("default-test-1",)
        ).fetchone()
        assert row["source_class"] == "external"

    def test_curated_default_is_zero(self, conn: sqlite3.Connection) -> None:
        """A freshly inserted row must have curated = 0."""
        upsert_insight(conn, _make_minimal_insight("default-test-2"))
        conn.commit()
        row = conn.execute(
            "SELECT curated FROM insights WHERE id = ?", ("default-test-2",)
        ).fetchone()
        assert row["curated"] == 0


# ---------------------------------------------------------------------------
# GAP_TYPES constant
# ---------------------------------------------------------------------------

class TestGapTypes:
    def test_gap_types_has_fourteen_values(self) -> None:
        """GAP_TYPES must have exactly 14 entries."""
        assert len(GAP_TYPES) == 14

    def test_gap_types_contains_expected_values(self) -> None:
        """Spot-check a few canonical values to confirm verbatim copy."""
        assert "metrics" in GAP_TYPES
        assert "economic_buyer" in GAP_TYPES
        assert "pricing_commercial" in GAP_TYPES
        assert "next_step" in GAP_TYPES
