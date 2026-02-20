#!/usr/bin/env python3
"""
SQLite access layer for Sales Coach database.

Provides schema initialization, FTS5 full-text search, and CRUD operations
for insights and sales methodologies.

Usage:
    from db import get_connection, init_db, search_insights

    init_db()  # Creates tables if not exist
    results = search_insights("discovery questions for CFO")
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from config import DB_PATH

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a connection with row factory and WAL mode enabled."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    influencer_slug TEXT NOT NULL,
    influencer_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    date_collected TEXT NOT NULL,
    primary_stage TEXT NOT NULL,
    secondary_stages TEXT,
    key_insight TEXT NOT NULL,
    tactical_steps TEXT,
    keywords TEXT,
    situation_examples TEXT,
    best_quote TEXT,
    relevance_score INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
    id, influencer_name, primary_stage, key_insight,
    tactical_steps, keywords, situation_examples, best_quote,
    content='insights', content_rowid='rowid'
);

-- FTS5 sync triggers (content= tables need manual sync)
CREATE TRIGGER IF NOT EXISTS insights_ai AFTER INSERT ON insights BEGIN
    INSERT INTO insights_fts(rowid, id, influencer_name, primary_stage,
        key_insight, tactical_steps, keywords, situation_examples, best_quote)
    VALUES (new.rowid, new.id, new.influencer_name, new.primary_stage,
        new.key_insight, new.tactical_steps, new.keywords,
        new.situation_examples, new.best_quote);
END;

CREATE TRIGGER IF NOT EXISTS insights_ad AFTER DELETE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, id, influencer_name,
        primary_stage, key_insight, tactical_steps, keywords,
        situation_examples, best_quote)
    VALUES ('delete', old.rowid, old.id, old.influencer_name,
        old.primary_stage, old.key_insight, old.tactical_steps,
        old.keywords, old.situation_examples, old.best_quote);
END;

CREATE TRIGGER IF NOT EXISTS insights_au AFTER UPDATE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, id, influencer_name,
        primary_stage, key_insight, tactical_steps, keywords,
        situation_examples, best_quote)
    VALUES ('delete', old.rowid, old.id, old.influencer_name,
        old.primary_stage, old.key_insight, old.tactical_steps,
        old.keywords, old.situation_examples, old.best_quote);
    INSERT INTO insights_fts(rowid, id, influencer_name, primary_stage,
        key_insight, tactical_steps, keywords, situation_examples, best_quote)
    VALUES (new.rowid, new.id, new.influencer_name, new.primary_stage,
        new.key_insight, new.tactical_steps, new.keywords,
        new.situation_examples, new.best_quote);
END;

CREATE TABLE IF NOT EXISTS methodologies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    author TEXT,
    source TEXT,
    category TEXT,
    overview TEXT NOT NULL,
    core_philosophy TEXT,
    when_to_use TEXT,
    strengths TEXT,
    limitations TEXT,
    deal_stages TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS methodology_components (
    id TEXT PRIMARY KEY,
    methodology_id TEXT NOT NULL REFERENCES methodologies(id),
    name TEXT NOT NULL,
    abbreviation TEXT,
    sequence_order INTEGER,
    description TEXT NOT NULL,
    how_to_execute TEXT,
    common_mistakes TEXT,
    example_scenario TEXT,
    keywords TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insight_methodology_tags (
    insight_id TEXT NOT NULL REFERENCES insights(id),
    component_id TEXT NOT NULL REFERENCES methodology_components(id),
    confidence REAL DEFAULT 0.0,
    tagged_by TEXT DEFAULT 'claude',
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (insight_id, component_id)
);

CREATE INDEX IF NOT EXISTS idx_insights_influencer ON insights(influencer_slug);
CREATE INDEX IF NOT EXISTS idx_insights_stage ON insights(primary_stage);
CREATE INDEX IF NOT EXISTS idx_insights_source_type ON insights(source_type);
CREATE INDEX IF NOT EXISTS idx_insights_relevance ON insights(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_tags_component ON insight_methodology_tags(component_id);
CREATE INDEX IF NOT EXISTS idx_tags_insight ON insight_methodology_tags(insight_id);
CREATE INDEX IF NOT EXISTS idx_components_methodology ON methodology_components(methodology_id);
"""


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


# ---------------------------------------------------------------------------
# Insights CRUD
# ---------------------------------------------------------------------------

def upsert_insight(conn: sqlite3.Connection, record: dict) -> None:
    """Insert or update a single insight record.

    Expects a dict with keys matching the insights table columns.
    JSON fields (secondary_stages, tactical_steps, keywords, situation_examples)
    should be Python lists — they'll be serialized to JSON strings.
    """
    json_fields = ["secondary_stages", "tactical_steps", "keywords", "situation_examples"]
    row = dict(record)
    for field in json_fields:
        val = row.get(field)
        if val is not None and not isinstance(val, str):
            row[field] = json.dumps(val)

    conn.execute(
        """
        INSERT INTO insights (
            id, influencer_slug, influencer_name, source_type, source_url,
            date_collected, primary_stage, secondary_stages, key_insight,
            tactical_steps, keywords, situation_examples, best_quote,
            relevance_score
        ) VALUES (
            :id, :influencer_slug, :influencer_name, :source_type, :source_url,
            :date_collected, :primary_stage, :secondary_stages, :key_insight,
            :tactical_steps, :keywords, :situation_examples, :best_quote,
            :relevance_score
        )
        ON CONFLICT(id) DO UPDATE SET
            influencer_name = excluded.influencer_name,
            primary_stage = excluded.primary_stage,
            secondary_stages = excluded.secondary_stages,
            key_insight = excluded.key_insight,
            tactical_steps = excluded.tactical_steps,
            keywords = excluded.keywords,
            situation_examples = excluded.situation_examples,
            best_quote = excluded.best_quote,
            relevance_score = excluded.relevance_score,
            updated_at = datetime('now')
        """,
        row,
    )


# ---------------------------------------------------------------------------
# Search (FTS5)
# ---------------------------------------------------------------------------

def search_insights(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    stage: Optional[str] = None,
    methodology_component: Optional[str] = None,
) -> list[dict]:
    """Full-text search across insights using FTS5.

    Args:
        query: Natural language search string (FTS5 handles tokenization).
        limit: Max results to return.
        stage: Optional filter by primary_stage.
        methodology_component: Optional filter by methodology component ID.

    Returns:
        List of insight dicts ordered by relevance.
    """
    # Build FTS5 match query — quote user input to avoid syntax errors
    fts_query = ' OR '.join(f'"{word}"' for word in query.split() if word.strip())
    if not fts_query:
        return []

    sql = """
        SELECT i.*, rank
        FROM insights_fts fts
        JOIN insights i ON i.rowid = fts.rowid
    """
    params: list = [fts_query]
    conditions = ["insights_fts MATCH ?"]

    if stage:
        conditions.append("i.primary_stage = ?")
        params.append(stage)

    if methodology_component:
        sql += " JOIN insight_methodology_tags t ON t.insight_id = i.id"
        conditions.append("t.component_id = ?")
        params.append(methodology_component)

    sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


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


# ---------------------------------------------------------------------------
# Methodology queries
# ---------------------------------------------------------------------------

def get_methodology_tree(conn: sqlite3.Connection) -> list[dict]:
    """Return all methodologies with their components nested.

    Returns:
        [{"id": "meddic", "name": "MEDDIC", ...,
          "components": [{"id": "meddic_metrics", ...}, ...]}, ...]
    """
    methodologies = conn.execute(
        "SELECT * FROM methodologies ORDER BY name"
    ).fetchall()

    result = []
    for m in methodologies:
        mdict = dict(m)
        components = conn.execute(
            "SELECT * FROM methodology_components WHERE methodology_id = ? ORDER BY sequence_order",
            (m["id"],),
        ).fetchall()
        mdict["components"] = [dict(c) for c in components]
        result.append(mdict)
    return result


def get_insights_by_methodology(
    conn: sqlite3.Connection,
    methodology_id: str,
    min_confidence: float = 0.5,
    limit: int = 50,
) -> list[dict]:
    """Return insights tagged with any component of a methodology."""
    rows = conn.execute(
        """
        SELECT DISTINCT i.*, t.component_id, t.confidence
        FROM insights i
        JOIN insight_methodology_tags t ON t.insight_id = i.id
        JOIN methodology_components mc ON mc.id = t.component_id
        WHERE mc.methodology_id = ?
          AND t.confidence >= ?
        ORDER BY t.confidence DESC
        LIMIT ?
        """,
        (methodology_id, min_confidence, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_tags_for_insights(
    conn: sqlite3.Connection,
    insight_ids: list[str],
) -> dict[str, list[dict]]:
    """Return methodology tags grouped by insight ID.

    Returns:
        {"insight_abc": [{"methodology": "MEDDIC", "component": "Champion", "confidence": 0.85}, ...]}
    """
    if not insight_ids:
        return {}
    placeholders = ",".join("?" for _ in insight_ids)
    rows = conn.execute(
        f"""
        SELECT t.insight_id, m.name AS methodology, mc.name AS component, t.confidence
        FROM insight_methodology_tags t
        JOIN methodology_components mc ON mc.id = t.component_id
        JOIN methodologies m ON m.id = mc.methodology_id
        WHERE t.insight_id IN ({placeholders})
          AND t.confidence >= 0.5
        ORDER BY t.confidence DESC
        """,  # noqa: S608
        insight_ids,
    ).fetchall()

    result: dict[str, list[dict]] = {}
    for row in rows:
        r = dict(row)
        iid = r.pop("insight_id")
        result.setdefault(iid, []).append(r)
    return result


def tag_insight_methodology(
    conn: sqlite3.Connection,
    insight_id: str,
    component_id: str,
    confidence: float,
    tagged_by: str = "claude",
) -> None:
    """Tag an insight with a methodology component."""
    conn.execute(
        """
        INSERT INTO insight_methodology_tags (insight_id, component_id, confidence, tagged_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(insight_id, component_id) DO UPDATE SET
            confidence = excluded.confidence,
            tagged_by = excluded.tagged_by
        """,
        (insight_id, component_id, confidence, tagged_by),
    )


# ---------------------------------------------------------------------------
# Methodology seeding
# ---------------------------------------------------------------------------

def upsert_methodology(conn: sqlite3.Connection, methodology: dict) -> None:
    """Insert or replace a methodology record."""
    conn.execute(
        """
        INSERT OR REPLACE INTO methodologies
            (id, name, author, source, category, overview, core_philosophy,
             when_to_use, strengths, limitations, deal_stages)
        VALUES (:id, :name, :author, :source, :category, :overview,
                :core_philosophy, :when_to_use, :strengths, :limitations,
                :deal_stages)
        """,
        methodology,
    )


def upsert_component(conn: sqlite3.Connection, component: dict) -> None:
    """Insert or replace a methodology component record."""
    row = dict(component)
    if "keywords" in row and not isinstance(row["keywords"], str):
        row["keywords"] = json.dumps(row["keywords"])
    conn.execute(
        """
        INSERT OR REPLACE INTO methodology_components
            (id, methodology_id, name, abbreviation, sequence_order,
             description, how_to_execute, common_mistakes, example_scenario,
             keywords)
        VALUES (:id, :methodology_id, :name, :abbreviation, :sequence_order,
                :description, :how_to_execute, :common_mistakes,
                :example_scenario, :keywords)
        """,
        row,
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(conn: sqlite3.Connection) -> dict:
    """Return counts for all tables."""
    stats = {}
    for table in ["insights", "methodologies", "methodology_components", "insight_methodology_tags"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        stats[table] = count
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    conn = get_connection()
    try:
        stats = get_stats(conn)
        print("=" * 50)
        print("SALES COACH DATABASE")
        print("=" * 50)
        for table, count in stats.items():
            print(f"  {table}: {count} records")
        print("=" * 50)
    finally:
        conn.close()
