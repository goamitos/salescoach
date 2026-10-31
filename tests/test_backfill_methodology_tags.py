"""Tests for methodology-tag selection and write-back (unit tests, no API calls)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from backfill_methodology_tags import (
    METHODOLOGY_TAG_VERSION,
    TAGGER,
    seed_cache,
    select_insights,
    write_insight_tags,
)
from db import (
    get_connection,
    init_db,
    tag_insight_methodology,
    upsert_component,
    upsert_insight,
    upsert_methodology,
)
from tag_cache import content_hash, ensure_tag_cache_table, needs_retag, record_tagged

COMPONENTS = {"meddic_champion", "spin_implication", "meddic_metrics"}


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    c = get_connection(db_path)
    upsert_methodology(c, {
        "id": "meddic", "name": "MEDDIC", "author": "a", "source": "s",
        "category": "c", "overview": "o", "core_philosophy": "p",
        "when_to_use": "w", "strengths": "[]", "limitations": "[]",
        "deal_stages": "[]",
    })
    for i, cid in enumerate(sorted(COMPONENTS)):
        upsert_component(c, {
            "id": cid, "methodology_id": "meddic", "name": cid,
            "abbreviation": "x", "sequence_order": i, "description": "d",
            "how_to_execute": "h", "common_mistakes": "m",
            "example_scenario": "e", "keywords": [],
        })
    ensure_tag_cache_table(c)
    c.commit()
    yield c
    c.close()


def _add(conn, iid: str, key_insight: str = "Insight") -> None:
    upsert_insight(conn, {
        "id": iid, "influencer_slug": "test", "influencer_name": "Test",
        "source_type": "linkedin", "source_url": f"https://x.com/{iid}",
        "date_collected": "2026-01-01", "primary_stage": "Discovery",
        "secondary_stages": [], "key_insight": key_insight,
        "tactical_steps": ["Step 1"], "keywords": ["test"],
        "situation_examples": ["Example"], "best_quote": "Quote",
        "relevance_score": 8,
    })
    conn.commit()


def _row(conn, iid: str) -> dict:
    return dict(conn.execute("SELECT * FROM insights WHERE id = ?", (iid,)).fetchone())


def _tags(conn, iid: str) -> set[str]:
    rows = conn.execute(
        "SELECT component_id FROM insight_methodology_tags WHERE insight_id = ?", (iid,)
    ).fetchall()
    return {r[0] for r in rows}


class TestSelectInsights:
    def test_seeded_tagged_insights_are_skipped(self, conn):
        _add(conn, "tagged")
        _add(conn, "untagged")
        tag_insight_methodology(conn, "tagged", "meddic_champion", 0.9)
        conn.commit()

        assert seed_cache(conn) == 1
        selected, deferred = select_insights(conn)
        assert [r["id"] for r in selected] == ["untagged"]
        assert deferred == 0

    def test_edited_insight_is_selected_again(self, conn):
        _add(conn, "a")
        record_tagged(conn, "a", content_hash(_row(conn, "a")), METHODOLOGY_TAG_VERSION, tagger=TAGGER)
        assert select_insights(conn)[0] == []

        _add(conn, "a", key_insight="Rewritten insight")
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_older_version_is_selected_again(self, conn):
        _add(conn, "a")
        record_tagged(conn, "a", content_hash(_row(conn, "a")), METHODOLOGY_TAG_VERSION - 1, tagger=TAGGER)
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_audience_cache_rows_do_not_count(self, conn):
        _add(conn, "a")
        record_tagged(conn, "a", content_hash(_row(conn, "a")), METHODOLOGY_TAG_VERSION, tagger="audience")
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_cap_reports_deferred(self, conn):
        for i in range(5):
            _add(conn, f"i{i}")
        selected, deferred = select_insights(conn, max_items=2)
        assert len(selected) == 2
        assert deferred == 3

    def test_force_selects_cached_insights_and_still_caps(self, conn):
        for i in range(3):
            _add(conn, f"i{i}")
            record_tagged(conn, f"i{i}", content_hash(_row(conn, f"i{i}")), METHODOLOGY_TAG_VERSION, tagger=TAGGER)
        assert select_insights(conn)[0] == []
        selected, deferred = select_insights(conn, force=True, max_items=2)
        assert len(selected) == 2
        assert deferred == 1


class TestWriteInsightTags:
    def test_retag_replaces_stale_components(self, conn):
        _add(conn, "a")
        tag_insight_methodology(conn, "a", "meddic_champion", 0.9)
        tag_insight_methodology(conn, "a", "spin_implication", 0.7)

        write_insight_tags(conn, _row(conn, "a"), [{"component_id": "meddic_metrics", "confidence": 0.8}], COMPONENTS)
        assert _tags(conn, "a") == {"meddic_metrics"}

    def test_records_insight_in_cache(self, conn):
        _add(conn, "a")
        insight = _row(conn, "a")
        write_insight_tags(conn, insight, [{"component_id": "meddic_champion", "confidence": 0.9}], COMPONENTS)
        assert needs_retag(conn, insight, METHODOLOGY_TAG_VERSION, tagger=TAGGER) is False

    def test_empty_result_is_recorded_so_it_is_not_resent(self, conn):
        _add(conn, "a")
        insight = _row(conn, "a")
        written, invalid = write_insight_tags(conn, insight, [], COMPONENTS)
        assert (written, invalid) == (0, 0)
        assert needs_retag(conn, insight, METHODOLOGY_TAG_VERSION, tagger=TAGGER) is False

    def test_invalid_and_low_confidence_tags_are_skipped(self, conn):
        _add(conn, "a")
        written, invalid = write_insight_tags(conn, _row(conn, "a"), [
            {"component_id": "made_up", "confidence": 0.9},
            {"component_id": "meddic_champion", "confidence": 0.3},
            {"component_id": "spin_implication", "confidence": 0.6},
        ], COMPONENTS)
        assert (written, invalid) == (1, 1)
        assert _tags(conn, "a") == {"spin_implication"}
