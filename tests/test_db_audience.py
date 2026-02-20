"""Tests for audience classification DB operations."""
import json
import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from db import get_connection, init_db, upsert_insight, search_leaders


@pytest.fixture
def db(tmp_path):
    """Create a fresh test database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db):
    """Get a connection to the test database."""
    c = get_connection(db)
    yield c
    c.close()


def _make_insight(id, **overrides):
    """Helper to build a minimal insight record."""
    record = {
        "id": id,
        "influencer_slug": "test-expert",
        "influencer_name": "Test Expert",
        "source_type": "linkedin",
        "source_url": f"https://example.com/{id}",
        "date_collected": "2026-01-01",
        "primary_stage": "Discovery",
        "secondary_stages": [],
        "key_insight": "Ask open-ended questions to uncover needs",
        "tactical_steps": ["Step 1", "Step 2"],
        "keywords": ["discovery", "questions"],
        "situation_examples": ["Meeting with CFO"],
        "best_quote": "Great quote",
        "relevance_score": 8,
    }
    record.update(overrides)
    return record


class TestAudienceColumns:
    def test_columns_exist(self, conn):
        """New audience columns exist after init_db."""
        row = conn.execute("PRAGMA table_info(insights)").fetchall()
        col_names = {r["name"] for r in row}
        assert "target_audience" in col_names
        assert "audience_confidence" in col_names
        assert "audience_reasoning" in col_names

    def test_upsert_preserves_audience(self, conn):
        """Upserting an insight doesn't clobber audience fields."""
        record = _make_insight("test-1")
        upsert_insight(conn, record)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["vp_sales", "cro"]), 0.9, "test-1"),
        )
        conn.commit()

        # Re-upsert same insight (simulating pipeline re-run)
        upsert_insight(conn, record)
        conn.commit()

        row = conn.execute("SELECT target_audience, audience_confidence FROM insights WHERE id = ?", ("test-1",)).fetchone()
        assert json.loads(row["target_audience"]) == ["vp_sales", "cro"]
        assert row["audience_confidence"] == 0.9


class TestSearchLeaders:
    def test_returns_only_leadership_insights(self, conn):
        """search_leaders only returns vp_sales/cro tagged insights."""
        vp = _make_insight("vp-1", key_insight="Build pipeline review cadence for your team")
        upsert_insight(conn, vp)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["vp_sales"]), 0.9, "vp-1"),
        )

        ae = _make_insight("ae-1", key_insight="Ask discovery questions to understand pain")
        upsert_insight(conn, ae)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["ae"]), 0.85, "ae-1"),
        )
        conn.commit()

        results = search_leaders(conn, "pipeline review")
        ids = {r["id"] for r in results}
        assert "vp-1" in ids
        assert "ae-1" not in ids

    def test_respects_confidence_threshold(self, conn):
        """Low-confidence VP tags are excluded."""
        low = _make_insight("low-1", key_insight="Coach your reps")
        upsert_insight(conn, low)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["vp_sales"]), 0.3, "low-1"),
        )
        conn.commit()

        results = search_leaders(conn, "coach reps", min_confidence=0.7)
        assert len(results) == 0

    def test_empty_query_returns_empty(self, conn):
        results = search_leaders(conn, "")
        assert results == []
