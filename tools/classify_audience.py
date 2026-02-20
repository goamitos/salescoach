#!/usr/bin/env python3
"""
Audience Classification with Claude Batch API

Re-classifies existing insights by target audience role
(vp_sales, cro, director, manager, ae, sdr, general).

Usage:
    python tools/classify_audience.py
    ./run.sh classify_audience
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

AUDIENCE_ROLES = """- vp_sales: VP Sales / CRO — managing teams, pipeline strategy, forecasting, coaching reps, board reporting, org design, hiring
- cro: Chief Revenue Officer — same as vp_sales (use vp_sales OR cro, never combine them)
- director: Sales Director — first-line leadership, deal coaching, team enablement
- manager: Sales Manager — rep development, frontline coaching, hiring
- ae: Account Executive — running deals, discovery calls, demos, negotiations, closing
- sdr: SDR / BDR — prospecting, cold outreach, booking meetings, lead qualification
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
