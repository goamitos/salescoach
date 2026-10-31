"""Tests for audience classification pipeline (unit tests, no API calls)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from classify_audience import (
    build_classification_prompt,
    parse_classification_response,
    select_insights,
    seed_cache,
    AUDIENCE_TAG_VERSION,
    TAGGER,
)
from tag_cache import content_hash, ensure_tag_cache_table, record_tagged
from db import get_connection, init_db, upsert_insight


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db):
    c = get_connection(db)
    ensure_tag_cache_table(c)
    yield c
    c.close()


class TestBuildPrompt:
    def test_includes_insight_fields(self):
        insight = {
            "key_insight": "Coach reps weekly",
            "tactical_steps": '["Review pipeline", "Role play"]',
            "keywords": '["coaching", "pipeline"]',
            "situation_examples": '["New VP onboarding"]',
            "primary_stage": "General Sales Mindset",
        }
        prompt = build_classification_prompt(insight)
        assert "Coach reps weekly" in prompt
        assert "vp_sales" in prompt
        assert "sdr" in prompt


class TestParseResponse:
    def test_valid_response(self):
        response_text = json.dumps({
            "target_audience": ["vp_sales", "director"],
            "confidence": 0.85,
            "reasoning": "Advice about managing a sales team",
        })
        result = parse_classification_response(response_text)
        assert result["target_audience"] == ["vp_sales", "director"]
        assert result["confidence"] == 0.85
        assert "managing" in result["reasoning"]

    def test_strips_markdown_fences(self):
        response_text = '```json\n{"target_audience": ["ae"], "confidence": 0.9, "reasoning": "Deal execution"}\n```'
        result = parse_classification_response(response_text)
        assert result["target_audience"] == ["ae"]

    def test_invalid_json_returns_none(self):
        result = parse_classification_response("not json at all")
        assert result is None


def _add(conn, iid, key_insight="Insight"):
    upsert_insight(conn, {
        "id": iid, "influencer_slug": "test", "influencer_name": "Test",
        "source_type": "linkedin", "source_url": f"https://x.com/{iid}",
        "date_collected": "2026-01-01", "primary_stage": "Discovery",
        "secondary_stages": [], "key_insight": key_insight,
        "tactical_steps": ["Step 1"], "keywords": ["test"],
        "situation_examples": ["Example"], "best_quote": "Quote",
        "relevance_score": 8,
    })


def _row(conn, iid):
    return dict(conn.execute("SELECT * FROM insights WHERE id = ?", (iid,)).fetchone())


class TestSelectInsights:
    def test_seeded_classified_insights_are_skipped(self, conn):
        for iid in ("tagged-1", "untagged-1"):
            _add(conn, iid)
        conn.execute(
            "UPDATE insights SET target_audience = ? WHERE id = ?",
            (json.dumps(["ae"]), "tagged-1"),
        )
        conn.commit()

        assert seed_cache(conn) == 1
        selected, deferred = select_insights(conn)
        ids = {r["id"] for r in selected}
        assert ids == {"untagged-1"}
        assert deferred == 0

    def test_edited_insight_is_selected_again(self, conn):
        _add(conn, "a")
        conn.commit()
        record_tagged(conn, "a", content_hash(_row(conn, "a")), AUDIENCE_TAG_VERSION, tagger=TAGGER)
        assert select_insights(conn)[0] == []

        _add(conn, "a", key_insight="Rewritten insight")
        conn.commit()
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_older_version_is_selected_again(self, conn):
        _add(conn, "a")
        conn.commit()
        record_tagged(conn, "a", content_hash(_row(conn, "a")), AUDIENCE_TAG_VERSION - 1, tagger=TAGGER)
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_methodology_cache_rows_do_not_count(self, conn):
        _add(conn, "a")
        conn.commit()
        record_tagged(conn, "a", content_hash(_row(conn, "a")), AUDIENCE_TAG_VERSION, tagger="methodology")
        assert [r["id"] for r in select_insights(conn)[0]] == ["a"]

    def test_cap_reports_deferred(self, conn):
        for i in range(5):
            _add(conn, f"i{i}")
        conn.commit()
        selected, deferred = select_insights(conn, max_items=2)
        assert len(selected) == 2
        assert deferred == 3
