"""Advice-library schema migration and constants.

Extends the insights table with the 3-axis categorization and provenance columns
needed for the output-quality intelligence layer (Phase 0, WS3.1).

This module does NOT tag or retrieve advice (that is WS3.2/WS4). It only manages
the schema shape and a user_version guard so re-tagging can be gated later.

GAP_TYPES is a verbatim copy of deal-bite's canonical gap taxonomy
(lib/dealbite/gap_taxonomy.py, locked 2026-06-11). Any change here requires a
corresponding bump in deal-bite and a schema version increment.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

ADVICE_SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Canonical gap taxonomy (verbatim copy from deal-bite gap_taxonomy.py)
# ---------------------------------------------------------------------------

GAP_TYPES: tuple[str, ...] = (
    "metrics",            # MEDDPICC M (rubric 1.1)
    "economic_buyer",     # MEDDPICC E (rubric 1.2)
    "decision_criteria",  # MEDDPICC D (rubric 1.3)
    "decision_process",   # MEDDPICC D (rubric 1.4)
    "paper_process",      # MEDDPICC P (rubric 1.5)
    "pain_implication",   # MEDDPICC I (1.6) plus Discovery Depth Dim 3
    "champion",           # MEDDPICC C (rubric 1.7)
    "competition",        # MEDDPICC C (rubric 1.8)
    "stakeholder_map",    # KYC 2.5, multithreading breadth (distinct from champion)
    "discovery_depth",    # Rubric Dimension 3
    "demo_quality",       # Rubric Dimension 4
    "business_case",      # Rubric Dimension 5
    "next_step",          # Bites process rule: every stage ends with a booked next stage
    "pricing_commercial", # Procurement and Negotiation stage
)

# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current PRAGMA user_version for the given connection."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Write version to PRAGMA user_version.

    PRAGMA user_version cannot be parameterized, so we validate the type
    and use an f-string to embed the literal integer.
    """
    if not isinstance(version, int):
        raise TypeError(f"version must be int, got {type(version).__name__}")
    conn.execute(f"PRAGMA user_version = {version}")


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("gap_type", "TEXT"),
    ("source_class", "TEXT DEFAULT 'external'"),
    ("curated", "INTEGER DEFAULT 0"),
    ("last_seen", "TEXT"),
    ("applicability", "TEXT"),
)


def migrate_advice_columns(db_path: Optional[Path] = None) -> None:
    """Add 3-axis categorization and provenance columns to the insights table.

    Safe to call repeatedly. Each column is added only if absent (guarded by
    PRAGMA table_info). Schema version is set to ADVICE_SCHEMA_VERSION on
    completion regardless of whether any columns were added.

    Args:
        db_path: Path to the SQLite database file. Defaults to the project DB
            when None (resolved inside tools.db.get_connection).
    """
    # Local import to avoid a circular dependency. Scripts run as
    # `python tools/x.py` have tools/ on sys.path, not the repo root.
    try:
        from db import get_connection
    except ImportError:
        from tools.db import get_connection

    conn = get_connection(db_path)
    try:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(insights)").fetchall()
        }
        for col, col_def in _NEW_COLUMNS:
            if col not in existing:
                conn.execute(f"ALTER TABLE insights ADD COLUMN {col} {col_def}")
                logger.info("Added column: %s", col)
            else:
                logger.debug("Column already present, skipping: %s", col)

        set_schema_version(conn, ADVICE_SCHEMA_VERSION)
        conn.commit()
        logger.info(
            "Advice schema migration complete (version=%d)", ADVICE_SCHEMA_VERSION
        )
    finally:
        conn.close()
