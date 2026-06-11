"""Tests for the versioned find_advice contract (Phase 0, WS4.1).

Covers:
- Results include rows whose FTS-indexed text matches requested gap terms
- curated=1 rows rank ahead of equal non-curated rows
- source_class filter excludes rows with a different source_class
- k caps the result count
- DB with user_version=0 (un-migrated) raises RuntimeError
- Required output fields are present in every result dict
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
    set_schema_version,
)
from advice import find_advice, FIND_ADVICE_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_insight(
    iid: str,
    stage: str = "Discovery",
    key_insight: str = "generic insight about discovery",
    relevance_score: int = 5,
    curated: int = 0,
    source_class: str = "external",
    gap_type: str | None = None,
) -> dict:
    return {
        "id": iid,
        "influencer_slug": "test-expert",
        "influencer_name": "Test Expert",
        "source_type": "linkedin",
        "source_url": f"https://example.com/{iid}",
        "date_collected": "2026-01-01",
        "primary_stage": stage,
        "secondary_stages": [],
        "key_insight": key_insight,
        "tactical_steps": ["Step A", "Step B"],
        "keywords": ["test"],
        "situation_examples": ["A CFO situation"],
        "best_quote": "A great quote",
        "relevance_score": relevance_score,
    }


def _set_extras(conn: sqlite3.Connection, iid: str, curated: int, source_class: str, gap_type: str | None) -> None:
    """Update advice-schema columns that upsert_insight does not handle."""
    conn.execute(
        "UPDATE insights SET curated=?, source_class=?, gap_type=? WHERE id=?",
        (curated, source_class, gap_type, iid),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Fully migrated temp database."""
    db_path = tmp_path / "test_advice.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db: Path):
    c = get_connection(db)
    yield c
    c.close()


@pytest.fixture
def seeded_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Connection with a small set of insight rows covering multiple scenarios."""
    rows = [
        # Row 1: matches 'economic buyer' terms, high relevance, NOT curated
        {
            **_minimal_insight(
                "eb-1",
                stage="Stakeholder Mapping",
                key_insight="Identify economic buyer authority budget decision maker early",
                relevance_score=8,
            )
        },
        # Row 2: matches 'economic buyer' terms, lower relevance, IS curated
        {
            **_minimal_insight(
                "eb-2",
                stage="Stakeholder Mapping",
                key_insight="Economic buyer must approve authority budget",
                relevance_score=5,
            )
        },
        # Row 3: matches 'champion' terms, internal source_class
        {
            **_minimal_insight(
                "ch-1",
                stage="Stakeholder Mapping",
                key_insight="Champion internal advocate sponsor enable prepare",
                relevance_score=7,
            )
        },
        # Row 4: completely unrelated — should NOT appear in economic_buyer results
        {
            **_minimal_insight(
                "unrelated-1",
                stage="Discovery",
                key_insight="Something entirely unrelated about quarterly reviews",
                relevance_score=9,
            )
        },
        # Row 5: matches 'pain' terms
        {
            **_minimal_insight(
                "pain-1",
                stage="Discovery",
                key_insight="Pain consequence cost of inaction urgency implication drives urgency",
                relevance_score=6,
            )
        },
    ]

    for row in rows:
        upsert_insight(conn, row)

    conn.commit()

    # Set extra columns after insert
    _set_extras(conn, "eb-1", curated=0, source_class="external", gap_type="economic_buyer")
    _set_extras(conn, "eb-2", curated=1, source_class="external", gap_type="economic_buyer")
    _set_extras(conn, "ch-1", curated=0, source_class="internal", gap_type="champion")
    _set_extras(conn, "unrelated-1", curated=0, source_class="external", gap_type=None)
    _set_extras(conn, "pain-1", curated=0, source_class="external", gap_type="pain_implication")

    return conn


# ---------------------------------------------------------------------------
# Contract version constant
# ---------------------------------------------------------------------------

class TestContractVersion:
    def test_contract_version_is_one(self) -> None:
        """FIND_ADVICE_CONTRACT_VERSION must be 1 for WS4.1."""
        assert FIND_ADVICE_CONTRACT_VERSION == 1


# ---------------------------------------------------------------------------
# Required output fields
# ---------------------------------------------------------------------------

class TestOutputFields:
    def test_required_fields_present_in_every_result(self, seeded_conn: sqlite3.Connection) -> None:
        """Every returned dict must include the six fields deal-bite's formatter reads."""
        required = {
            "influencer_name",
            "primary_stage",
            "key_insight",
            "tactical_steps",
            "best_quote",
            "situation_examples",
        }
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer"])
        assert len(results) > 0, "Expected at least one result for 'economic_buyer'"
        for r in results:
            for field in required:
                assert field in r, f"Field '{field}' missing from result: {r.keys()}"


# ---------------------------------------------------------------------------
# Gap term filtering
# ---------------------------------------------------------------------------

class TestGapFiltering:
    def test_economic_buyer_gaps_return_relevant_rows(self, seeded_conn: sqlite3.Connection) -> None:
        """economic_buyer results must include rows whose text matches EB search terms."""
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer"])
        ids = {r["id"] for r in results}
        assert "eb-1" in ids or "eb-2" in ids, (
            f"Expected eb-1 or eb-2 in results; got {ids}"
        )

    def test_unrelated_row_not_in_economic_buyer_results(self, seeded_conn: sqlite3.Connection) -> None:
        """The 'unrelated-1' row must not appear in economic_buyer results."""
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer"])
        ids = {r["id"] for r in results}
        assert "unrelated-1" not in ids

    def test_pain_implication_gap_returns_pain_row(self, seeded_conn: sqlite3.Connection) -> None:
        """pain_implication gap should surface the pain-1 row."""
        results = find_advice(seeded_conn, stage=None, gaps=["pain_implication"])
        ids = {r["id"] for r in results}
        assert "pain-1" in ids, f"Expected pain-1 in results; got {ids}"


# ---------------------------------------------------------------------------
# Curated ranking
# ---------------------------------------------------------------------------

class TestCuratedRanking:
    def test_curated_rows_rank_ahead_of_non_curated(self, seeded_conn: sqlite3.Connection) -> None:
        """eb-2 (curated=1, relevance=5) must rank ahead of eb-1 (curated=0, relevance=8)."""
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer"])
        ids = [r["id"] for r in results if r["id"] in ("eb-1", "eb-2")]
        assert len(ids) >= 2, f"Expected both eb-1 and eb-2 in results; got {ids}"
        assert ids[0] == "eb-2", (
            f"curated eb-2 should be first; got order {ids}"
        )


# ---------------------------------------------------------------------------
# source_class filter
# ---------------------------------------------------------------------------

class TestSourceClassFilter:
    def test_source_class_external_excludes_internal_row(self, seeded_conn: sqlite3.Connection) -> None:
        """Filtering source_class='external' must exclude ch-1 (which is 'internal')."""
        results = find_advice(
            seeded_conn,
            stage=None,
            gaps=["champion"],
            source_class="external",
        )
        ids = {r["id"] for r in results}
        assert "ch-1" not in ids, f"Internal row ch-1 should be excluded; got {ids}"

    def test_no_source_class_filter_includes_internal_row(self, seeded_conn: sqlite3.Connection) -> None:
        """Without a source_class filter, ch-1 (internal) should appear in champion results."""
        results = find_advice(seeded_conn, stage=None, gaps=["champion"])
        ids = {r["id"] for r in results}
        assert "ch-1" in ids, f"Expected ch-1 in unfiltered results; got {ids}"


# ---------------------------------------------------------------------------
# k cap
# ---------------------------------------------------------------------------

class TestKCap:
    def test_k_caps_result_count(self, seeded_conn: sqlite3.Connection) -> None:
        """Results must not exceed k rows."""
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer", "pain_implication"], k=2)
        assert len(results) <= 2, f"Expected <= 2 results with k=2; got {len(results)}"

    def test_k_one_returns_at_most_one(self, seeded_conn: sqlite3.Connection) -> None:
        """k=1 must return at most 1 row."""
        results = find_advice(seeded_conn, stage=None, gaps=["economic_buyer"], k=1)
        assert len(results) <= 1


# ---------------------------------------------------------------------------
# Schema version guard
# ---------------------------------------------------------------------------

class TestSchemaVersionGuard:
    def test_raises_runtime_error_when_user_version_is_zero(self, tmp_path: Path) -> None:
        """find_advice must raise RuntimeError when user_version < ADVICE_SCHEMA_VERSION."""
        db_path = tmp_path / "old.db"
        # Init a DB but then forcibly reset user_version to 0 to simulate un-migrated state
        init_db(db_path)
        conn = get_connection(db_path)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

        with pytest.raises(RuntimeError, match="[Ss]chema"):
            find_advice(conn, stage=None, gaps=["economic_buyer"])

        conn.close()

    def test_does_not_raise_when_schema_version_is_current(self, seeded_conn: sqlite3.Connection) -> None:
        """find_advice must not raise when user_version >= ADVICE_SCHEMA_VERSION."""
        # Should not raise
        find_advice(seeded_conn, stage=None, gaps=["economic_buyer"])
