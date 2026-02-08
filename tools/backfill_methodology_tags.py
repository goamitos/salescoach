#!/usr/bin/env python3
"""
Backfill methodology tags for all insights using Claude Batch API.

Sends each insight to Claude Haiku to identify matching methodology
components, then writes tags to insight_methodology_tags table.

Usage:
    python backfill_methodology_tags.py              # Full backfill
    python backfill_methodology_tags.py --dry-run    # Preview cost estimate
    python backfill_methodology_tags.py --resume BATCH_ID  # Resume polling

Cost estimate: ~1,893 requests × Haiku Batch pricing ≈ $0.19
"""

import json
import logging
import sys
import time
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, TMP_DIR
from db import (
    get_connection,
    init_db,
    get_methodology_tree,
    tag_insight_methodology,
    get_stats,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds between batch status checks
RESULTS_FILE = TMP_DIR / "methodology_tags_results.json"

TAGGING_PROMPT = """Analyze this sales insight and identify which sales methodology components it relates to.

INSIGHT:
Influencer: {influencer}
Stage: {stage}
Key Insight: {key_insight}
Tactical Steps: {tactical_steps}
Keywords: {keywords}
Best Quote: {best_quote}

METHODOLOGY COMPONENTS (only tag if genuinely relevant, not just keyword overlap):
{components_list}

Respond in JSON format only (no markdown, no explanation):
{{
  "tags": [
    {{"component_id": "meddic_champion", "confidence": 0.85}},
    {{"component_id": "spin_implication", "confidence": 0.6}}
  ]
}}

Rules:
- Only include tags with confidence >= 0.5
- Maximum 5 tags per insight (most insights will have 1-3)
- Confidence 0.8+: insight directly teaches or demonstrates this component
- Confidence 0.6-0.8: insight is clearly related to this component
- Confidence 0.5-0.6: insight touches on this component
- Return {{"tags": []}} if no methodology components apply
- Consider the full meaning, not just keyword matches
"""


def build_components_list(tree: list[dict]) -> str:
    """Format methodology components for the tagging prompt."""
    lines = []
    for m in tree:
        for c in m["components"]:
            kw = json.loads(c["keywords"]) if isinstance(c["keywords"], str) else (c["keywords"] or [])
            lines.append(
                f"{m['name']} > {c['name']} (id: {c['id']}): {', '.join(kw)}"
            )
    return "\n".join(lines)


def build_batch_requests(
    insights: list[dict], components_list: str
) -> list[dict]:
    """Build Batch API request objects for all insights."""
    requests = []
    for insight in insights:
        # Parse JSON fields
        tactical = insight.get("tactical_steps", "")
        if tactical and tactical.startswith("["):
            try:
                tactical = ", ".join(json.loads(tactical))
            except json.JSONDecodeError:
                pass

        keywords = insight.get("keywords", "")
        if keywords and keywords.startswith("["):
            try:
                keywords = ", ".join(json.loads(keywords))
            except json.JSONDecodeError:
                pass

        prompt = TAGGING_PROMPT.format(
            influencer=insight["influencer_name"],
            stage=insight["primary_stage"],
            key_insight=insight["key_insight"],
            tactical_steps=tactical,
            keywords=keywords,
            best_quote=insight.get("best_quote", ""),
            components_list=components_list,
        )

        requests.append({
            "custom_id": insight["id"],
            "params": {
                "model": CLAUDE_MODEL,
                "max_tokens": 300,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
        })
    return requests


def backfill_tags() -> None:
    """Run the full backfill: submit batch, poll, write tags."""
    dry_run = "--dry-run" in sys.argv
    resume_batch_id = None

    if "--resume" in sys.argv:
        idx = sys.argv.index("--resume")
        if idx + 1 < len(sys.argv):
            resume_batch_id = sys.argv[idx + 1]

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set. Run via ./run.sh or set in .env")
        return

    init_db()
    conn = get_connection()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        # Load methodology components for prompt
        tree = get_methodology_tree(conn)
        components_list = build_components_list(tree)
        total_components = sum(len(m["components"]) for m in tree)
        logger.info("Loaded %d methodology components for tagging", total_components)

        # Load insights (skip already-tagged ones unless --force)
        if "--force" in sys.argv:
            insights = [dict(r) for r in conn.execute("SELECT * FROM insights").fetchall()]
        else:
            insights = [dict(r) for r in conn.execute(
                """SELECT i.* FROM insights i
                   WHERE i.id NOT IN (SELECT DISTINCT insight_id FROM insight_methodology_tags)"""
            ).fetchall()]

        logger.info("Found %d insights to tag", len(insights))

        if not insights:
            logger.info("All insights already tagged. Use --force to re-tag.")
            return

        # Cost estimate
        avg_input_tokens = 800  # ~prompt with components list
        avg_output_tokens = 100  # ~JSON response
        # Haiku Batch: input $0.04/MTok, output $0.20/MTok
        estimated_cost = (
            len(insights) * avg_input_tokens * 0.04
            + len(insights) * avg_output_tokens * 0.20
        ) / 1_000_000
        logger.info("Estimated cost: $%.2f (%d requests, Haiku Batch pricing)", estimated_cost, len(insights))

        if dry_run:
            print("=" * 50)
            print("DRY RUN — No API calls made")
            print("=" * 50)
            print(f"  Insights to tag: {len(insights)}")
            print(f"  Components available: {total_components}")
            print(f"  Estimated cost: ${estimated_cost:.2f}")
            print("=" * 50)
            return

        # Submit or resume batch
        if resume_batch_id:
            logger.info("Resuming batch %s...", resume_batch_id)
            batch_id = resume_batch_id
        else:
            batch_requests = build_batch_requests(insights, components_list)
            logger.info("Submitting batch of %d requests...", len(batch_requests))
            batch = client.messages.batches.create(requests=batch_requests)
            batch_id = batch.id
            logger.info("Batch created: %s", batch_id)

        # Poll for completion
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
            done = counts.succeeded + counts.errored + counts.canceled + counts.expired
            logger.info(
                "Batch %s: %s (%d/%d done, %d succeeded, %d errored)",
                batch_id, batch.processing_status,
                done, total, counts.succeeded, counts.errored,
            )
            if batch.processing_status == "ended":
                break
            time.sleep(POLL_INTERVAL)

        # Process results
        logger.info("Batch complete, processing results...")
        tags_written = 0
        insights_tagged = 0
        invalid_ids = 0
        errors = 0

        # Load valid component IDs to filter out hallucinated ones
        valid_component_ids = {
            row[0] for row in conn.execute("SELECT id FROM methodology_components").fetchall()
        }

        for entry in client.messages.batches.results(batch_id):
            insight_id = entry.custom_id

            if entry.result.type != "succeeded":
                errors += 1
                continue

            try:
                text = entry.result.message.content[0].text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text[:-3].strip()

                result = json.loads(text)
                tags = result.get("tags", [])

                if tags:
                    insight_had_valid_tag = False
                    for tag in tags:
                        component_id = tag.get("component_id", "")
                        confidence = tag.get("confidence", 0.0)

                        if component_id not in valid_component_ids:
                            invalid_ids += 1
                            continue

                        if confidence >= 0.5:
                            tag_insight_methodology(
                                conn, insight_id, component_id, confidence
                            )
                            tags_written += 1
                            insight_had_valid_tag = True

                    if insight_had_valid_tag:
                        insights_tagged += 1

            except (json.JSONDecodeError, KeyError) as e:
                errors += 1
                logger.debug("Parse error for %s: %s", insight_id, e)

        if invalid_ids:
            logger.warning("Skipped %d tags with invalid component IDs", invalid_ids)

        conn.commit()

        stats = get_stats(conn)
        print("=" * 50)
        print("METHODOLOGY TAGGING COMPLETE")
        print("=" * 50)
        print(f"  Insights tagged:  {insights_tagged}")
        print(f"  Tags written:     {tags_written}")
        print(f"  Errors:           {errors}")
        print(f"  Avg tags/insight: {tags_written / max(insights_tagged, 1):.1f}")
        print(f"  DB total tags:    {stats['insight_methodology_tags']}")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == "__main__":
    backfill_tags()
