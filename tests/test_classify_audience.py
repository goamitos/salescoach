"""Tests for audience classification pipeline (unit tests, no API calls)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from classify_audience import (
    build_classification_prompt,
    parse_classification_response,
    get_unclassified_insights,
)
from db import get_connection, init_db, upsert_insight


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def conn(db):
    c = get_connection(db)
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


class TestGetUnclassified:
    def test_returns_only_untagged(self, conn):
        for id in ("tagged-1", "untagged-1"):
            upsert_insight(conn, {
                "id": id, "influencer_slug": "test", "influencer_name": "Test",
                "source_type": "linkedin", "source_url": f"https://x.com/{id}",
                "date_collected": "2026-01-01", "primary_stage": "Discovery",
                "secondary_stages": [], "key_insight": "Insight",
                "tactical_steps": ["Step 1"], "keywords": ["test"],
                "situation_examples": ["Example"], "best_quote": "Quote",
                "relevance_score": 8,
            })
        conn.execute(
            "UPDATE insights SET target_audience = ? WHERE id = ?",
            (json.dumps(["ae"]), "tagged-1"),
        )
        conn.commit()

        unclassified = get_unclassified_insights(conn)
        ids = {r["id"] for r in unclassified}
        assert "untagged-1" in ids
        assert "tagged-1" not in ids
