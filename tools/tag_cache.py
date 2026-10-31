"""Content-hash tag cache for the advice-library tagging guard (Phase 0, WS3.2).

Provides a cost guard so each insight is tagged once and only re-tagged when
its content changes or the tag-schema version bumps. A per-run item cap
prevents silent truncation by surfacing the deferred count to the caller.

This module does NOT call any LLM. Cache rows are namespaced per tagger, so
one tagger recording an insight never marks it done for another.

Callers:
    tools/backfill_methodology_tags.py  (tagger="methodology")
    tools/classify_audience.py          (tagger="audience")

Each caller passes its own prompt-version constant, not ADVICE_SCHEMA_VERSION:
bump the tagger's constant when its prompt changes to force a re-tag.

Usage:
    conn = get_connection(db_path)
    ensure_tag_cache_table(conn)

    to_tag, deferred = select_for_tagging(
        conn, all_insights, MY_TAG_VERSION, max_items=500, tagger="mine"
    )
    for insight in to_tag:
        # ... call LLM here ...
        record_tagged(conn, insight["id"], content_hash(insight), MY_TAG_VERSION, tagger="mine")
    conn.commit()

When wiring a tagger into a DB that already holds its tags, call
seed_from_existing() first, otherwise every insight looks untagged and the
first run re-tags everything.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

# Fields that define tagging-relevant content.
_TAGGING_FIELDS: tuple[str, ...] = ("key_insight", "tactical_steps", "keywords")


def content_hash(insight: dict) -> str:
    """Return a stable SHA-256 hex digest over tagging-relevant insight fields.

    Only key_insight, tactical_steps, and keywords are included. The hash is
    independent of dict key order and stable across interpreter restarts.

    Normalization rules:
    - list fields: serialized via json.dumps with sort_keys=True
    - None fields: treated as empty string ""
    - str fields: used as-is

    Args:
        insight: An insight dict (may contain any keys).

    Returns:
        64-character lowercase hex digest string.
    """
    parts: list[str] = []
    for field in _TAGGING_FIELDS:
        value = insight.get(field)
        if value is None:
            normalized = ""
        elif isinstance(value, list):
            normalized = json.dumps(value, sort_keys=True, ensure_ascii=False)
        else:
            normalized = str(value)
        parts.append(f"{field}:{normalized}")

    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ensure_tag_cache_table(conn: sqlite3.Connection) -> None:
    """Create the tag_cache table if it does not already exist.

    Safe to call repeatedly (idempotent). Does not commit; the caller controls
    the transaction boundary.

    Table schema:
        insight_id TEXT NOT NULL
        tagger TEXT NOT NULL DEFAULT 'default'
        content_hash TEXT NOT NULL
        schema_version INTEGER NOT NULL
        tagged_at TEXT DEFAULT (datetime('now'))
        PRIMARY KEY (insight_id, tagger)

    Args:
        conn: An open SQLite connection.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_cache (
            insight_id     TEXT    NOT NULL,
            tagger         TEXT    NOT NULL DEFAULT 'default',
            content_hash   TEXT    NOT NULL,
            schema_version INTEGER NOT NULL,
            tagged_at      TEXT    DEFAULT (datetime('now')),
            PRIMARY KEY (insight_id, tagger)
        )
        """
    )


def needs_retag(
    conn: sqlite3.Connection,
    insight: dict,
    current_schema_version: int,
    tagger: str = "default",
) -> bool:
    """Return True if the insight should be (re-)tagged.

    An insight needs tagging when any of the following is true:
    1. No cache row exists for insight['id'].
    2. The stored content_hash differs from content_hash(insight).
    3. The stored schema_version is less than current_schema_version.

    Args:
        conn: An open SQLite connection with tag_cache present.
        insight: An insight dict; must contain 'id'.
        current_schema_version: The active tag version for this tagger.
        tagger: Cache namespace; each tagger keeps its own rows.

    Returns:
        True if the insight needs (re-)tagging, False otherwise.
    """
    row = conn.execute(
        "SELECT content_hash, schema_version FROM tag_cache"
        " WHERE insight_id = ? AND tagger = ?",
        (insight["id"], tagger),
    ).fetchone()

    if row is None:
        return True

    current_hash = content_hash(insight)
    stored_hash, stored_version = row[0], row[1]

    if stored_hash != current_hash:
        return True

    if stored_version < current_schema_version:
        return True

    return False


def record_tagged(
    conn: sqlite3.Connection,
    insight_id: str,
    hash_value: str,
    schema_version: int,
    tagger: str = "default",
) -> None:
    """Upsert a tag_cache row to record that an insight has been tagged.

    Uses INSERT ... ON CONFLICT DO UPDATE so it is safe to call for both new
    and previously-cached insights. Does not commit; the caller controls the
    transaction boundary.

    Args:
        conn: An open SQLite connection with tag_cache present.
        insight_id: The insight's primary-key string.
        hash_value: The content hash returned by content_hash().
        schema_version: The schema version under which the insight was tagged.
        tagger: Cache namespace; each tagger keeps its own rows.
    """
    conn.execute(
        """
        INSERT INTO tag_cache (insight_id, tagger, content_hash, schema_version, tagged_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(insight_id, tagger) DO UPDATE SET
            content_hash   = excluded.content_hash,
            schema_version = excluded.schema_version,
            tagged_at      = datetime('now')
        """,
        (insight_id, tagger, hash_value, schema_version),
    )


def seed_from_existing(
    conn: sqlite3.Connection,
    insights: list[dict],
    schema_version: int,
    tagger: str = "default",
) -> int:
    """Record already-tagged insights in the cache without calling any LLM.

    Use once when wiring a tagger into a DB that already holds its tags, so
    the first cached run does not re-tag everything. Idempotent: re-running
    overwrites rows with the same values. Does not commit.

    Args:
        conn: An open SQLite connection with tag_cache present.
        insights: Insights the caller has confirmed are already tagged.
        schema_version: The tag version to record them under.
        tagger: Cache namespace; each tagger keeps its own rows.

    Returns:
        Number of insights recorded.
    """
    for ins in insights:
        record_tagged(conn, ins["id"], content_hash(ins), schema_version, tagger=tagger)
    logger.info("Seeded tag cache: %d insights for tagger %r.", len(insights), tagger)
    return len(insights)


def select_for_tagging(
    conn: sqlite3.Connection,
    insights: list[dict],
    current_schema_version: int,
    max_items: int,
    tagger: str = "default",
) -> tuple[list[dict], int]:
    """Filter insights to those that need tagging, respecting a per-run item cap.

    Filters the input list to insights where needs_retag() is True, then
    applies max_items as a hard cap. The deferred_count is always surfaced so
    the caller knows how many insights were skipped -- no silent truncation.

    Logs at INFO:
    - how many insights need tagging in total
    - how many are being tagged this run
    - how many are deferred until the next run

    Args:
        conn: An open SQLite connection with tag_cache present.
        insights: Full list of insight dicts to evaluate.
        current_schema_version: Active tag-schema version.
        max_items: Maximum number of insights to return for tagging this run.
        tagger: Cache namespace; each tagger keeps its own rows.

    Returns:
        A tuple of (selected, deferred_count) where:
        - selected: list of up to max_items insights that need tagging
        - deferred_count: number of insights that needed tagging but were not
          selected due to the cap (always >= 0)
    """
    needing_tag = [
        ins for ins in insights
        if needs_retag(conn, ins, current_schema_version, tagger=tagger)
    ]

    total_needing = len(needing_tag)
    selected = needing_tag[:max_items]
    tagging_this_run = len(selected)
    deferred_count = max(0, total_needing - max_items)

    logger.info(
        "Tag selection [%s]: %d insights need tagging; tagging %d this run; %d deferred.",
        tagger,
        total_needing,
        tagging_this_run,
        deferred_count,
    )

    return selected, deferred_count
