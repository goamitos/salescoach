# VP/CRO Content Hub — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add audience classification to all 1,893 insights, then expose VP/CRO content via CLI (`coach` command) and Streamlit (Leadership Hub tab).

**Architecture:** Claude Haiku Batch API classifies existing insights by target audience (vp_sales, cro, director, manager, ae, sdr, general). New columns on the `insights` table store the classification. CLI and Streamlit query the VP/CRO subset via FTS5 with audience filter.

**Tech Stack:** Python 3.10+, anthropic SDK (Batch API), SQLite FTS5, Streamlit, argparse

---

## Task 1: DB Schema Migration

Add three new columns to the `insights` table and a helper function to query VP/CRO content.

**Files:**
- Modify: `tools/db.py:47-150` (SCHEMA_SQL and new functions)
- Test: `tests/test_db_audience.py`

**Step 1: Write the failing test**

Create `tests/test_db_audience.py`:

```python
"""Tests for audience classification DB operations."""
import json
import sqlite3
from pathlib import Path

import pytest

# Import from tools/ — add to sys.path
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


def _make_insight(id, audience=None, confidence=None, reasoning=None, **overrides):
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
    return record, audience, confidence, reasoning


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
        record, *_ = _make_insight("test-1")
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
        # Insert VP insight
        vp, *_ = _make_insight("vp-1", key_insight="Build pipeline review cadence for your team")
        upsert_insight(conn, vp)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["vp_sales"]), 0.9, "vp-1"),
        )

        # Insert AE insight
        ae, *_ = _make_insight("ae-1", key_insight="Ask discovery questions to understand pain")
        upsert_insight(conn, ae)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["ae"]), 0.85, "ae-1"),
        )
        conn.commit()

        results = search_leaders(conn, "pipeline review")
        assert len(results) >= 1
        ids = {r["id"] for r in results}
        assert "vp-1" in ids
        assert "ae-1" not in ids

    def test_respects_confidence_threshold(self, conn):
        """Low-confidence VP tags are excluded."""
        low, *_ = _make_insight("low-1", key_insight="Coach your reps")
        upsert_insight(conn, low)
        conn.execute(
            "UPDATE insights SET target_audience = ?, audience_confidence = ? WHERE id = ?",
            (json.dumps(["vp_sales"]), 0.3, "low-1"),
        )
        conn.commit()

        results = search_leaders(conn, "coach reps", min_confidence=0.7)
        assert len(results) == 0

    def test_empty_query_returns_empty(self, conn):
        """Empty query returns no results."""
        results = search_leaders(conn, "")
        assert results == []
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_db_audience.py -x -v`
Expected: FAIL — `search_leaders` not defined, columns don't exist

**Step 3: Add audience columns to SCHEMA_SQL and new functions**

In `tools/db.py`, add to the end of `SCHEMA_SQL` (before the closing `"""`):

```python
# After the existing CREATE INDEX statements, add:

-- Audience classification columns (added via ALTER for existing DBs)
-- New DBs get these via init_db; existing DBs get them via migrate_audience_columns()
```

Add a migration function and search_leaders function after `init_db`:

```python
def migrate_audience_columns(db_path: Optional[Path] = None) -> None:
    """Add audience columns to existing databases. Safe to call repeatedly."""
    conn = get_connection(db_path)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
        for col, col_type in [
            ("target_audience", "TEXT"),
            ("audience_confidence", "REAL"),
            ("audience_reasoning", "TEXT"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE insights ADD COLUMN {col} {col_type}")
                logger.info("Added column: %s", col)
        conn.commit()
    finally:
        conn.close()


def search_leaders(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    stage: Optional[str] = None,
    min_confidence: float = 0.7,
) -> list[dict]:
    """Search insights tagged for VP Sales / CRO audience.

    Uses FTS5 for text matching, filters to records where target_audience
    contains 'vp_sales' or 'cro' with confidence >= min_confidence.
    """
    fts_query = ' OR '.join(f'"{word}"' for word in query.split() if word.strip())
    if not fts_query:
        return []

    sql = """
        SELECT i.*, rank
        FROM insights_fts fts
        JOIN insights i ON i.rowid = fts.rowid
        WHERE insights_fts MATCH ?
          AND i.audience_confidence >= ?
          AND (
              i.target_audience LIKE '%"vp_sales"%'
              OR i.target_audience LIKE '%"cro"%'
          )
    """
    params: list = [fts_query, min_confidence]

    if stage:
        sql += " AND i.primary_stage = ?"
        params.append(stage)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
```

Also update `init_db` to call `migrate_audience_columns` after schema creation:

```python
def init_db(db_path: Optional[Path] = None) -> None:
    """Create all tables, indexes, and triggers if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialized at %s", db_path or DB_PATH)
    finally:
        conn.close()
    migrate_audience_columns(db_path)
```

Update `upsert_insight` ON CONFLICT clause — do NOT overwrite audience fields:

The current ON CONFLICT updates most fields. The audience fields (`target_audience`, `audience_confidence`, `audience_reasoning`) are NOT in the INSERT column list, so they default to NULL on first insert and won't be touched on conflict. No change needed — the migration adds nullable columns that existing UPSERTs won't touch.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_db_audience.py -x -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add tools/db.py tests/test_db_audience.py
git commit -m "feat: add audience classification columns and search_leaders query"
```

---

## Task 2: Audience Classification Script

Batch-classify all existing insights using Claude Haiku Batch API.

**Files:**
- Create: `tools/classify_audience.py`
- Test: `tests/test_classify_audience.py`

**Step 1: Write the failing test**

Create `tests/test_classify_audience.py`:

```python
"""Tests for audience classification pipeline (unit tests, no API calls)."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
        # Insert two insights
        for id in ("tagged-1", "untagged-1"):
            upsert_insight(conn, {
                "id": id, "influencer_slug": "test", "influencer_name": "Test",
                "source_type": "linkedin", "source_url": f"https://x.com/{id}",
                "date_collected": "2026-01-01", "primary_stage": "Discovery",
                "key_insight": "Insight", "relevance_score": 8,
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_classify_audience.py -x -v`
Expected: FAIL — `classify_audience` module not found

**Step 3: Write classify_audience.py**

Create `tools/classify_audience.py`:

```python
#!/usr/bin/env python3
"""
Audience Classification with Claude Batch API

Re-classifies existing insights by target audience role
(vp_sales, cro, director, manager, ae, sdr, general).

Usage:
    python tools/classify_audience.py
    # or via run.sh:
    ./run.sh classify_audience

Input:  SQLite database (data/sales_coach.db)
Output: Updates target_audience, audience_confidence, audience_reasoning columns
"""
import json
import logging
import time
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, DB_PATH
from db import get_connection, migrate_audience_columns

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 30

AUDIENCE_ROLES = """- vp_sales / cro: Managing teams, pipeline strategy, forecasting, coaching reps, board reporting, org design, hiring
- director / manager: First-line leadership, deal coaching, team enablement, rep development
- ae: Running deals, discovery calls, demos, negotiations, closing, account management
- sdr: Prospecting, cold outreach, booking meetings, lead qualification
- general: Applicable across all roles equally"""

CLASSIFICATION_PROMPT = """Classify who this sales insight is most useful for.
The question is: "Who would act on this advice?"

INSIGHT: {key_insight}
TACTICAL STEPS: {tactical_steps}
KEYWORDS: {keywords}
SITUATION EXAMPLES: {situation_examples}
DEAL STAGE: {primary_stage}

TARGET AUDIENCE ROLES:
{roles}

Respond in JSON only (no markdown):
{{"target_audience": ["role1", "role2"], "confidence": 0.85, "reasoning": "One sentence why"}}

Rules:
- Return 1-3 roles (most specific to least)
- Confidence 0.0-1.0 reflects how clearly this targets a specific audience vs being general
- If content could apply to anyone, return ["general"] with lower confidence
- "vp_sales" and "cro" are for content about BEING a leader, not selling TO leaders"""


def build_classification_prompt(insight: dict) -> str:
    """Build the classification prompt for one insight."""
    return CLASSIFICATION_PROMPT.format(
        key_insight=insight.get("key_insight", ""),
        tactical_steps=insight.get("tactical_steps", ""),
        keywords=insight.get("keywords", ""),
        situation_examples=insight.get("situation_examples", ""),
        primary_stage=insight.get("primary_stage", ""),
        roles=AUDIENCE_ROLES,
    )


def parse_classification_response(response_text: str) -> Optional[dict]:
    """Parse Claude's JSON response into audience classification."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        return {
            "target_audience": data["target_audience"],
            "confidence": float(data["confidence"]),
            "reasoning": data["reasoning"],
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def get_unclassified_insights(conn) -> list[dict]:
    """Get all insights that haven't been audience-classified yet."""
    rows = conn.execute(
        "SELECT * FROM insights WHERE target_audience IS NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def classify_all():
    """Main: batch-classify all untagged insights."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set")
        return

    migrate_audience_columns()

    conn = get_connection()
    unclassified = get_unclassified_insights(conn)

    if not unclassified:
        logger.info("All insights already classified")
        conn.close()
        return

    logger.info("Found %d unclassified insights", len(unclassified))

    # Estimate cost
    est_input = len(unclassified) * 400
    est_output = len(unclassified) * 80
    est_cost = (est_input * 0.40 + est_output * 2.00) / 1_000_000
    logger.info("Estimated cost: $%.2f (Haiku Batch)", est_cost)

    # Build batch requests
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    requests = []
    for insight in unclassified:
        prompt = build_classification_prompt(insight)
        requests.append({
            "custom_id": insight["id"],
            "params": {
                "model": CLAUDE_MODEL,
                "max_tokens": 200,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
        })

    logger.info("Submitting batch of %d requests...", len(requests))
    batch = client.messages.batches.create(requests=requests)
    logger.info("Batch created: %s", batch.id)

    # Poll for completion
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        total = done + counts.processing
        logger.info(
            "Batch %s: %s (%d/%d done, %d succeeded, %d errored)",
            batch.id, batch.processing_status, done, total,
            counts.succeeded, counts.errored,
        )
        if batch.processing_status == "ended":
            break
        time.sleep(POLL_INTERVAL)

    # Process results
    updated = 0
    errors = 0
    for entry in client.messages.batches.results(batch.id):
        if entry.result.type != "succeeded":
            errors += 1
            continue

        response_text = entry.result.message.content[0].text
        parsed = parse_classification_response(response_text)
        if not parsed:
            errors += 1
            logger.warning("Parse error for %s", entry.custom_id)
            continue

        conn.execute(
            """UPDATE insights
               SET target_audience = ?, audience_confidence = ?, audience_reasoning = ?
               WHERE id = ?""",
            (
                json.dumps(parsed["target_audience"]),
                parsed["confidence"],
                parsed["reasoning"],
                entry.custom_id,
            ),
        )
        updated += 1

    conn.commit()
    conn.close()
    logger.info("Classification complete: %d updated, %d errors", updated, errors)


if __name__ == "__main__":
    classify_all()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_classify_audience.py -x -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add tools/classify_audience.py tests/test_classify_audience.py
git commit -m "feat: add audience classification script using Claude Batch API"
```

---

## Task 3: Run the Classification Batch

This is a manual execution step — no code changes, just running the pipeline.

**Step 1: Run the classification**

```bash
./run.sh classify_audience
```

Expected: Submits batch, polls until complete, updates ~1,893 records. Takes ~5-15 min. Cost ~$0.60.

**Step 2: Verify results**

```bash
cd tools && python3 -c "
from db import get_connection, DB_PATH
conn = get_connection()
total = conn.execute('SELECT COUNT(*) FROM insights').fetchone()[0]
classified = conn.execute('SELECT COUNT(*) FROM insights WHERE target_audience IS NOT NULL').fetchone()[0]
vp_cro = conn.execute(\"\"\"
    SELECT COUNT(*) FROM insights
    WHERE (target_audience LIKE '%\"vp_sales\"%' OR target_audience LIKE '%\"cro\"%')
      AND audience_confidence >= 0.7
\"\"\").fetchone()[0]
print(f'Total: {total}, Classified: {classified}, VP/CRO (>=0.7): {vp_cro}')
conn.close()
"
```

Expected: All records classified, some meaningful subset tagged VP/CRO.

**Step 3: Commit DB state note**

No code to commit — the DB is in `.gitignore`. But log the results count in a commit message note if meaningful.

---

## Task 4: CLI — `search_leaders.py`

**Files:**
- Create: `tools/search_leaders.py`
- Test: `tests/test_search_leaders_cli.py`

**Step 1: Write the failing test**

Create `tests/test_search_leaders_cli.py`:

```python
"""Tests for search_leaders CLI (argument parsing, no API calls)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from search_leaders import parse_args


class TestParseArgs:
    def test_basic_query(self):
        args = parse_args(["pipeline review"])
        assert args.query == "pipeline review"
        assert args.ask is False

    def test_ask_mode(self):
        args = parse_args(["--ask", "how to run forecast"])
        assert args.ask is True
        assert args.query == "how to run forecast"

    def test_stage_filter(self):
        args = parse_args(["--stage", "Discovery", "coaching"])
        assert args.stage == "Discovery"
        assert args.query == "coaching"

    def test_influencer_filter(self):
        args = parse_args(["--influencer", "Ian Koniak", "quota"])
        assert args.influencer == "Ian Koniak"

    def test_default_confidence(self):
        args = parse_args(["test"])
        assert args.min_confidence == 0.7
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_search_leaders_cli.py -x -v`
Expected: FAIL — module not found

**Step 3: Write search_leaders.py**

Create `tools/search_leaders.py`:

```python
#!/usr/bin/env python3
"""
Search Leaders — VP/CRO Content Search & AI Q&A

Searches the VP Sales / CRO subset of the Sales Coach knowledge base.
Optionally synthesizes AI coaching advice from leadership-relevant insights.

Usage:
    python tools/search_leaders.py "pipeline review"
    python tools/search_leaders.py --ask "how to build a forecast process"
    python tools/search_leaders.py --stage Discovery "coaching reps"
    # or via run.sh:
    ./run.sh search_leaders "query"
    ./run.sh search_leaders --ask "question"
"""
import argparse
import json
import sys

import anthropic

from config import ANTHROPIC_API_KEY, DB_PATH
from db import get_connection, search_leaders


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Search VP/CRO sales leadership content",
    )
    parser.add_argument("query", help="Search query or question")
    parser.add_argument(
        "--ask", action="store_true",
        help="AI synthesis mode: get a Claude-powered answer from VP/CRO content",
    )
    parser.add_argument("--stage", type=str, default=None, help="Filter by deal stage")
    parser.add_argument("--influencer", type=str, default=None, help="Filter by influencer name")
    parser.add_argument(
        "--min-confidence", type=float, default=0.7,
        help="Minimum audience confidence threshold (default: 0.7)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    return parser.parse_args(argv)


def display_results(results):
    """Print search results in readable format."""
    if not results:
        print("\nNo VP/CRO leadership content found for this query.")
        print("Try broader keywords or lower --min-confidence.")
        return

    print(f"\n{'='*60}")
    print(f"LEADERSHIP INSIGHTS ({len(results)} results)")
    print(f"{'='*60}")

    for i, r in enumerate(results, 1):
        audience = json.loads(r.get("target_audience") or "[]")
        confidence = r.get("audience_confidence", 0)
        print(f"\n--- [{i}] {r.get('influencer_name', 'Unknown')} ({r.get('primary_stage', 'General')}) ---")
        print(f"Audience: {', '.join(audience)} (confidence: {confidence:.0%})")
        print(f"Insight: {r.get('key_insight', '')}")

        steps = r.get("tactical_steps", "")
        if steps:
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except json.JSONDecodeError:
                    steps = [steps]
            if isinstance(steps, list):
                for step in steps:
                    print(f"  • {step}")

        quote = r.get("best_quote", "")
        if quote:
            print(f'  "{quote}"')

        url = r.get("source_url", "")
        if url:
            print(f"  Source: {url}")


def synthesize_answer(query, results):
    """Use Claude to synthesize an answer from VP/CRO results."""
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set — cannot synthesize.")
        return

    if not results:
        print("\nNo VP/CRO content to synthesize from.")
        return

    # Build context from results
    context_parts = []
    for r in results:
        name = r.get("influencer_name", "Unknown")
        stage = r.get("primary_stage", "General")
        insight = r.get("key_insight", "")
        steps = r.get("tactical_steps", "")
        quote = r.get("best_quote", "")
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                steps = [steps]
        steps_str = ", ".join(steps) if isinstance(steps, list) else str(steps)
        part = f"**{name}** ({stage}): {insight}"
        if steps_str:
            part += f"\nSteps: {steps_str}"
        if quote:
            part += f'\nQuote: "{quote}"'
        context_parts.append(part)

    context = "\n\n---\n\n".join(context_parts)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system = """You are a sales leadership coach specializing in advice for VP Sales and CRO roles.
You synthesize wisdom from top sales leaders to provide actionable advice for sales executives.
Focus on leadership, team management, strategy, and organizational decisions — not individual deal tactics.
Reference which expert's wisdom you're drawing from."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{
            "role": "user",
            "content": f'A sales leader asks:\n\n"{query}"\n\nBased on these leadership insights:\n\n{context}\n\nProvide specific, actionable advice for a VP Sales or CRO.',
        }],
    )

    print(f"\n{'='*60}")
    print("LEADERSHIP COACHING")
    print(f"{'='*60}\n")
    print(response.content[0].text)

    print(f"\n{'='*60}")
    print(f"Sources: {len(results)} VP/CRO insights used")
    print(f"{'='*60}")
    for r in results:
        name = r.get("influencer_name", "Unknown")
        insight = r.get("key_insight", "")[:80]
        print(f"  • {name}: {insight}...")


def main():
    args = parse_args()
    conn = get_connection()

    results = search_leaders(
        conn, args.query,
        limit=args.limit,
        stage=args.stage,
        min_confidence=args.min_confidence,
    )

    # Optional: filter by influencer name (post-query)
    if args.influencer:
        results = [
            r for r in results
            if args.influencer.lower() in r.get("influencer_name", "").lower()
        ]

    if args.ask:
        synthesize_answer(args.query, results)
    else:
        display_results(results)

    conn.close()


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_search_leaders_cli.py -x -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add tools/search_leaders.py tests/test_search_leaders_cli.py
git commit -m "feat: add search_leaders CLI for VP/CRO content search and AI Q&A"
```

---

## Task 5: `coach` CLI Entry Point

A shell wrapper that injects 1Password secrets and dispatches to the right tool.

**Files:**
- Create: `coach.sh` (project root)
- Modify: `run.sh` (add search_leaders and coach entry)

**Step 1: Create coach.sh**

```bash
#!/bin/bash
# coach — Unified CLI for Sales Coach AI
#
# Usage:
#   coach ask "question"                    # General Q&A
#   coach leaders "query"                   # Search VP/CRO content
#   coach leaders --ask "question"          # AI-synthesized leadership advice
#   coach search --stage Discovery "query"  # Filtered search

set -e
cd "$(dirname "$0")"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

if [ -z "$1" ]; then
    echo "Usage: coach <command> [options] <query>"
    echo ""
    echo "Commands:"
    echo "  ask        General sales coaching Q&A"
    echo "  leaders    Search VP/CRO leadership content"
    echo "  search     Search all content with filters"
    echo ""
    echo "Examples:"
    echo "  coach ask 'how to handle objections'"
    echo "  coach leaders 'pipeline review cadence'"
    echo "  coach leaders --ask 'first 90 days as CRO'"
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    ask)
        op run --env-file=.env.tpl -- python3 tools/ask_coach.py "$@"
        ;;
    leaders)
        op run --env-file=.env.tpl -- python3 tools/search_leaders.py "$@"
        ;;
    search)
        # Future: general search with filters
        op run --env-file=.env.tpl -- python3 tools/search_leaders.py "$@"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available: ask, leaders, search"
        exit 1
        ;;
esac
```

**Step 2: Make executable and test**

```bash
chmod +x coach.sh
./coach.sh  # Should print usage
```

**Step 3: Add symlink setup**

```bash
# Optional: symlink to /usr/local/bin for global access
# ln -sf "$(pwd)/coach.sh" /usr/local/bin/coach
```

**Step 4: Commit**

```bash
git add coach.sh
git commit -m "feat: add coach CLI entry point with 1Password secret injection"
```

---

## Task 6: Streamlit Leadership Hub Page

**Files:**
- Create: `pages/4_leaders.py`
- Modify: `streamlit_app.py:82-98` (add tab)
- Modify: `utils/data.py` (add audience-filtered loading)

**Step 1: Add audience-filtered data loader to utils/data.py**

Add to `utils/data.py` after `search_insights_fts`:

```python
@st.cache_data(ttl=300)
def load_leader_insights() -> list[dict]:
    """Load insights tagged for VP Sales / CRO audience."""
    conn = _get_db_connection()
    if not conn:
        return []
    try:
        rows = conn.execute("""
            SELECT * FROM insights
            WHERE (target_audience LIKE '%"vp_sales"%' OR target_audience LIKE '%"cro"%')
              AND audience_confidence >= 0.7
            ORDER BY relevance_score DESC
        """).fetchall()
        insights = []
        for row in rows:
            insight = dict(row)
            for field in ("secondary_stages", "tactical_steps", "keywords",
                          "situation_examples", "target_audience"):
                val = insight.get(field)
                if val and isinstance(val, str):
                    try:
                        insight[field] = json.loads(val)
                    except json.JSONDecodeError:
                        insight[field] = [] if field != "target_audience" else []
            insights.append(insight)
        conn.close()
        return insights
    except Exception:
        conn.close()
        return []


def get_leader_stats(insights: list[dict]) -> dict:
    """Compute aggregate stats for the Leadership Hub dashboard."""
    if not insights:
        return {"total": 0, "by_stage": {}, "by_influencer": {}, "top_keywords": []}

    by_stage: dict[str, int] = {}
    by_influencer: dict[str, int] = {}
    keyword_counts: dict[str, int] = {}

    for i in insights:
        stage = i.get("primary_stage", "General")
        by_stage[stage] = by_stage.get(stage, 0) + 1

        name = i.get("influencer_name", "Unknown")
        by_influencer[name] = by_influencer.get(name, 0) + 1

        for kw in (i.get("keywords") or []):
            if isinstance(kw, str):
                keyword_counts[kw.lower()] = keyword_counts.get(kw.lower(), 0) + 1

    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "total": len(insights),
        "by_stage": dict(sorted(by_stage.items(), key=lambda x: x[1], reverse=True)),
        "by_influencer": dict(sorted(by_influencer.items(), key=lambda x: x[1], reverse=True)[:15]),
        "top_keywords": top_keywords,
    }
```

**Step 2: Create the Leadership Hub page**

Create `pages/4_leaders.py`:

```python
"""Leadership Hub — VP Sales & CRO Insights.

Browse, search, and get AI coaching from leadership-tagged content.
"""
from __future__ import annotations

import json

import streamlit as st

from utils.data import (
    load_leader_insights,
    load_insights,
    get_leader_stats,
    get_stage_color,
    filter_insights,
    load_influencers,
)
from utils.search import find_relevant_insights, build_context
from utils.ai import get_coaching_advice, get_anthropic_key

# ── Load Data ─────────────────────────────────────────
leader_insights = load_leader_insights()
all_insights = load_insights()
stats = get_leader_stats(leader_insights)

# ── Header ────────────────────────────────────────────
st.markdown("## Leadership Hub")
st.markdown(f"**{stats['total']}** insights for VP Sales & CRO roles (from {len(all_insights)} total)")

# ── Stats Dashboard ───────────────────────────────────
if stats["total"] > 0:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### By Deal Stage")
        for stage, count in list(stats["by_stage"].items())[:8]:
            pct = count / stats["total"] * 100
            st.markdown(f"**{stage}**: {count} ({pct:.0f}%)")

    with col2:
        st.markdown("#### Top Contributors")
        for name, count in list(stats["by_influencer"].items())[:8]:
            st.markdown(f"**{name}**: {count} insights")

    if stats["top_keywords"]:
        st.markdown("#### Top Keywords")
        kw_display = ", ".join(f"**{kw}** ({c})" for kw, c in stats["top_keywords"][:12])
        st.markdown(kw_display)

    st.divider()

# ── Filters & Search ──────────────────────────────────
col_search, col_stage, col_expert = st.columns([3, 1, 1])

with col_search:
    search_query = st.text_input("Search leadership insights", placeholder="pipeline review, forecast, coaching...")

with col_stage:
    stages = ["All"] + list(stats["by_stage"].keys())
    selected_stage = st.selectbox("Stage", stages)

with col_expert:
    influencers = ["All"] + list(stats["by_influencer"].keys())
    selected_expert = st.selectbox("Expert", influencers)

# Apply filters
filtered = leader_insights
if search_query:
    query_lower = search_query.lower()
    keywords = [w for w in query_lower.split() if len(w) > 2]
    filtered = [
        i for i in filtered
        if any(
            kw in (i.get("key_insight", "") + " " +
                   i.get("best_quote", "") + " " +
                   " ".join(i.get("keywords") or []) + " " +
                   " ".join(i.get("tactical_steps") or [])).lower()
            for kw in keywords
        )
    ]
if selected_stage != "All":
    filtered = [i for i in filtered if i.get("primary_stage") == selected_stage]
if selected_expert != "All":
    filtered = [i for i in filtered if i.get("influencer_name") == selected_expert]

st.markdown(f"**{len(filtered)}** insights matching filters")

# ── Browse Results ────────────────────────────────────
for insight in filtered[:30]:
    stage = insight.get("primary_stage", "General")
    name = insight.get("influencer_name", "Unknown")
    key = insight.get("key_insight", "")
    audience = insight.get("target_audience", [])
    if isinstance(audience, str):
        try:
            audience = json.loads(audience)
        except json.JSONDecodeError:
            audience = []
    confidence = insight.get("audience_confidence", 0)

    with st.expander(f"**{name}** — {key[:80]}{'...' if len(key) > 80 else ''}", expanded=False):
        st.markdown(f"**Stage:** {stage} | **Audience:** {', '.join(audience)} ({confidence:.0%})")
        st.markdown(f"**Insight:** {key}")

        steps = insight.get("tactical_steps") or []
        if steps:
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except json.JSONDecodeError:
                    steps = [steps]
            st.markdown("**Tactical Steps:**")
            for step in steps:
                st.markdown(f"- {step}")

        quote = insight.get("best_quote", "")
        if quote:
            st.markdown(f'> "{quote}"')

        url = insight.get("source_url", "")
        if url:
            st.markdown(f"[Source]({url})")

# ── AI Q&A ────────────────────────────────────────────
st.divider()
st.markdown("### Ask About Leadership")

leader_question = st.text_input(
    "Ask a leadership question",
    placeholder="How should I structure my first 90 days as a new VP Sales?",
    key="leader_question",
)

if leader_question and st.button("Get Leadership Advice", key="leader_ask_btn"):
    with st.spinner("Synthesizing leadership insights..."):
        relevant = find_relevant_insights(leader_insights, leader_question, top_n=8)
        if relevant:
            context = build_context(relevant)
            advice = get_coaching_advice(
                leader_question, context, chat_history=[], persona=None,
            )
            st.markdown(advice)

            with st.expander("Sources used"):
                for r in relevant:
                    name = r.get("influencer_name", "Unknown")
                    insight = r.get("key_insight", "")[:80]
                    st.markdown(f"- **{name}**: {insight}...")
        else:
            st.warning("No matching leadership insights found. Try different keywords.")
```

**Step 3: Add Leaders tab to streamlit_app.py**

In `streamlit_app.py`, update the tab columns and add the Leaders button and page loader.

Change line 82:
```python
col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
```
to:
```python
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 5])
```

Add after the col3 block (after line 97):
```python
with col4:
    if st.button("👔 Leaders", key="tab_leaders", use_container_width=True):
        st.query_params["page"] = "leaders"
        st.rerun()
```

Rename old col4 to col5 (empty spacer column — no code references it).

Add a new elif block after the insights page loader (after line 134):
```python
elif current_tab == "leaders":
    import importlib.util
    spec = importlib.util.spec_from_file_location("leaders_page", "pages/4_leaders.py")
    leaders_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(leaders_module)
```

**Step 4: Verify it loads**

```bash
./run.sh streamlit
# Navigate to Leaders tab
```

**Step 5: Commit**

```bash
git add pages/4_leaders.py utils/data.py streamlit_app.py
git commit -m "feat: add Leadership Hub tab with stats, browse, and AI Q&A"
```

---

## Task 7: Forward Integration — Update process_content.py

Add audience classification to the processing prompt so new content is tagged automatically.

**Files:**
- Modify: `tools/process_content.py:54-79` (ANALYSIS_PROMPT)

**Step 1: Update the prompt**

In `tools/process_content.py`, update `ANALYSIS_PROMPT` to include audience classification. Add to the JSON response format:

```
  "target_audience": ["role1"],
  "audience_confidence": 0.85
```

And add to the prompt text:

```
Target audience roles (who would act on this advice?):
- vp_sales/cro: Team management, pipeline strategy, forecasting, coaching reps
- director/manager: First-line leadership, deal coaching, enablement
- ae: Running deals, discovery, demos, closing
- sdr: Prospecting, cold outreach, booking meetings
- general: Applicable across all roles
```

**Step 2: Update the result processing**

In the result processing section (~line 259-266), ensure `target_audience` and `audience_confidence` are passed through to the output.

**Step 3: Update push_airtable.py**

In `tools/push_airtable.py`, when building the insight record for SQLite upsert, include the new fields if present in the processed data:

```python
if "target_audience" in item:
    record["target_audience"] = json.dumps(item["target_audience"]) if isinstance(item["target_audience"], list) else item["target_audience"]
    record["audience_confidence"] = item.get("audience_confidence")
```

**Step 4: Verify existing tests still pass**

Run: `python3 -m pytest tests/ --tb=short -q`
Expected: All tests pass

**Step 5: Commit**

```bash
git add tools/process_content.py tools/push_airtable.py
git commit -m "feat: add audience classification to content processing pipeline"
```

---

## Task 8: Final Verification

**Step 1: Run full test suite**

```bash
python3 -m pytest tests/ --tb=short -q
```

**Step 2: Test CLI end-to-end**

```bash
./coach.sh leaders "pipeline review"
./coach.sh leaders --ask "how to structure my first 90 days as VP Sales"
./coach.sh ask "discovery questions for a CFO"
```

**Step 3: Test Streamlit**

```bash
./run.sh streamlit
# Verify all 4 tabs work: Coach, Experts, Insights, Leaders
```

**Step 4: Final commit and push**

```bash
git push
```
