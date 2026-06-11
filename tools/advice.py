"""Versioned find_advice contract for the Salescoach advice library.

Contract version: FIND_ADVICE_CONTRACT_VERSION = 1

Inputs:
  conn               -- open sqlite3.Connection to a fully migrated DB
                        (PRAGMA user_version >= ADVICE_SCHEMA_VERSION)
  stage              -- optional deal stage string (used as context hint, not a hard filter)
  gaps               -- list of canonical gap_type strings (members of GAP_TYPES)
  methodology_focus  -- optional free-text (injected into FTS alongside gap terms)
  source_class       -- optional; when given, only rows with this source_class are returned
  k                  -- max rows to return (default 5)

Outputs:
  list of dicts, each containing at minimum:
    influencer_name, primary_stage, key_insight,
    tactical_steps, best_quote, situation_examples
  Ordered by: curated DESC, gap_type-match boost, preferred-stage match,
              relevance_score DESC, FTS rank.

Version guarantee:
  Callers must check that FIND_ADVICE_CONTRACT_VERSION matches whatever version
  they were built against. A schema too old to satisfy the contract raises
  RuntimeError so callers can degrade rather than return garbage.
"""
from __future__ import annotations

import sqlite3
import logging
from typing import Optional

from advice_schema import ADVICE_SCHEMA_VERSION, GAP_TYPES, get_schema_version

logger = logging.getLogger(__name__)

FIND_ADVICE_CONTRACT_VERSION: int = 1

# ---------------------------------------------------------------------------
# Internal gap-to-search-term map
# ---------------------------------------------------------------------------

_GAP_SEARCH_TERMS: dict[str, str] = {
    "metrics": "metrics success criteria quantify KPI measurable outcome",
    "economic_buyer": "economic buyer authority budget decision maker",
    "decision_criteria": "decision criteria requirements evaluation scorecard",
    "decision_process": "decision process steps timeline approval sequence",
    "paper_process": "paper process procurement legal security review contract signature",
    "pain_implication": "pain consequence cost of inaction impact urgency implication",
    "champion": "champion internal advocate sponsor enable prepare",
    "competition": "competitive incumbent differentiation alternative status quo",
    "stakeholder_map": "stakeholder multithread buying committee executive engage",
    "discovery_depth": "discovery question needs uncover qualify budget timeline",
    "demo_quality": "demo customize value KPI present connect buyer data",
    "business_case": "business case ROI financial value justify",
    "next_step": "next step close agenda book meeting schedule commit follow through",
    "pricing_commercial": "pricing negotiate budget commercial terms discount",
}

_GAP_PREFERRED_STAGE: dict[str, str] = {
    "metrics": "Business Case Development",
    "economic_buyer": "Stakeholder Mapping",
    "decision_criteria": "Needs Analysis",
    "decision_process": "Procurement & Negotiation",
    "paper_process": "Procurement & Negotiation",
    "pain_implication": "Discovery",
    "champion": "Stakeholder Mapping",
    "competition": "Needs Analysis",
    "stakeholder_map": "Stakeholder Mapping",
    "discovery_depth": "Discovery",
    "demo_quality": "Demo & Presentation",
    "business_case": "Business Case Development",
    "next_step": "Demo & Presentation",
    "pricing_commercial": "Procurement & Negotiation",
}


def _build_fts_query(gaps: list[str], methodology_focus: Optional[str]) -> str:
    """Build an FTS5 MATCH expression from gap search terms plus optional focus text.

    Each word is double-quoted to avoid FTS5 syntax errors from special characters.
    Terms from all requested gaps are OR-ed together.
    """
    words: list[str] = []
    for gap in gaps:
        terms = _GAP_SEARCH_TERMS.get(gap, gap.replace("_", " "))
        words.extend(terms.split())
    if methodology_focus:
        words.extend(methodology_focus.split())
    # deduplicate while preserving order
    seen: set[str] = set()
    unique_words: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique_words.append(w)
    # Strip inner double-quotes before wrapping so a token like '"challenger"'
    # cannot produce a nested-quote FTS expression.
    return " OR ".join(f'"{w.replace(chr(34), "")}"' for w in unique_words if w.strip())


def find_advice(
    conn: sqlite3.Connection,
    *,
    stage: Optional[str],
    gaps: list[str],
    methodology_focus: Optional[str] = None,
    source_class: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    """Return up to k advice rows relevant to the given gap types.

    Raises:
        RuntimeError: if the DB's user_version is below ADVICE_SCHEMA_VERSION,
            indicating the schema has not been fully migrated.
    """
    current_version = get_schema_version(conn)
    if current_version < ADVICE_SCHEMA_VERSION:
        raise RuntimeError(
            f"Schema version {current_version} is below the required "
            f"ADVICE_SCHEMA_VERSION={ADVICE_SCHEMA_VERSION}. "
            "Run init_db or migrate_advice_columns before calling find_advice."
        )

    if not gaps:
        return []

    fts_query = _build_fts_query(gaps, methodology_focus)
    if not fts_query:
        return []

    preferred_stages = {_GAP_PREFERRED_STAGE[g] for g in gaps if g in _GAP_PREFERRED_STAGE}
    gap_set = set(gaps)

    sql = """
        SELECT i.*,
               rank AS fts_rank,
               CASE WHEN i.curated = 1 THEN 1 ELSE 0 END AS curated_boost,
               CASE WHEN i.gap_type IN ({gap_placeholders}) THEN 1 ELSE 0 END AS gap_boost,
               CASE WHEN i.primary_stage IN ({stage_placeholders}) THEN 1 ELSE 0 END AS stage_boost
        FROM insights_fts fts
        JOIN insights i ON i.rowid = fts.rowid
        WHERE insights_fts MATCH ?
    """

    params: list = [fts_query]

    gap_placeholders = ",".join("?" for _ in gap_set) if gap_set else "NULL"
    stage_placeholders = ",".join("?" for _ in preferred_stages) if preferred_stages else "NULL"

    sql = sql.replace("{gap_placeholders}", gap_placeholders)
    sql = sql.replace("{stage_placeholders}", stage_placeholders)

    if gap_set:
        params.extend(gap_set)
    if preferred_stages:
        params.extend(preferred_stages)

    if source_class is not None:
        sql += " AND i.source_class = ?"
        params.append(source_class)

    sql += """
        ORDER BY
            curated_boost DESC,
            gap_boost DESC,
            stage_boost DESC,
            i.relevance_score DESC,
            fts_rank
        LIMIT ?
    """
    params.append(k)

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        logger.warning("find_advice SQL error: %s", exc)
        return []

    return [dict(row) for row in rows]
