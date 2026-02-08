#!/usr/bin/env python3
"""
Content Processing with Claude Batch API

Analyzes collected content, categorizes by deal stage,
and extracts structured insights using the Batch API
(50% cost reduction, no rate limiting needed).

Usage:
    python tools/process_content.py

Input:
    .tmp/linkedin_raw.json
    .tmp/youtube_raw.json

Output:
    .tmp/processed_content.json
"""
import hashlib
import json
import time
from typing import Any, Optional
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from config import (
    TMP_DIR,
    ANTHROPIC_API_KEY,
    RELEVANCE_THRESHOLD,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TEMPERATURE,
    DEAL_STAGES,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# File paths
LINKEDIN_FILE = TMP_DIR / "linkedin_raw.json"
YOUTUBE_FILE = TMP_DIR / "youtube_raw.json"
OUTPUT_FILE = TMP_DIR / "processed_content.json"

# Batch polling interval (seconds)
POLL_INTERVAL = 30

# Analysis prompt
ANALYSIS_PROMPT = """Analyze this sales content and extract structured insights.

CONTENT:
{content}

SOURCE: {source_type} by {influencer}

Available deal stages: {stages}

Respond in JSON format only (no markdown, no explanation):
{{
  "primary_stage": "One of the deal stages listed above",
  "secondary_stages": ["Up to 2 additional relevant stages"],
  "key_insight": "One sentence summary of the main wisdom",
  "tactical_steps": ["2-4 actionable steps from the content"],
  "keywords": ["5-8 searchable keywords"],
  "situation_examples": ["1-2 specific scenarios where this applies"],
  "best_quote": "Most memorable/quotable line from content",
  "relevance_score": 1-10
}}

Scoring guide:
- 8-10: Highly tactical, specific, immediately actionable
- 6-7: Good general advice with some specifics
- 4-5: Tangentially related or too generic
- 1-3: Not relevant to sales execution"""


def load_collected_content() -> list[dict]:
    """Load content from LinkedIn and YouTube collection files."""
    content_items = []

    # Load LinkedIn posts
    if LINKEDIN_FILE.exists():
        with open(LINKEDIN_FILE) as f:
            data = json.load(f)
            for post in data.get("posts", []):
                url = post.get("url", "")
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                content_items.append(
                    {
                        "id": f"li_{url_hash}",
                        "content": post.get("content", ""),
                        "influencer": post.get("influencer", "Unknown"),
                        "source_type": "linkedin",
                        "source_url": url,
                        "date_collected": post.get("date_collected", ""),
                    }
                )
        logger.info(f"Loaded {len(data.get('posts', []))} LinkedIn posts")

    # Load YouTube transcripts
    if YOUTUBE_FILE.exists():
        with open(YOUTUBE_FILE) as f:
            data = json.load(f)
            for video in data.get("videos", []):
                for chunk in video.get("transcript_chunks", []):
                    content_items.append(
                        {
                            "id": f"yt_{video.get('video_id')}_{chunk.get('chunk_index')}",
                            "content": chunk.get("content", ""),
                            "influencer": video.get("influencer", "Unknown"),
                            "source_type": "youtube",
                            "source_url": video.get("url", ""),
                            "date_collected": video.get("date_collected", ""),
                        }
                    )
        logger.info(f"Loaded {len(data.get('videos', []))} YouTube videos")

    return content_items


def load_existing_processed() -> tuple[list[dict[str, any]], set[str]]:
    """Load existing processed content to avoid reprocessing and preserve data."""
    existing = []
    seen_ids = set()

    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE) as f:
                data = json.load(f)
                existing = data.get("processed", [])
                seen_ids = {item.get("source_id") for item in existing}
                logger.info(f"Loaded {len(existing)} existing processed items")
        except Exception as e:
            logger.warning(f"Could not load existing data: {e}")

    return existing, seen_ids


def build_batch_requests(items: list[dict]) -> list[dict]:
    """Build Batch API request objects from content items."""
    requests = []
    for item in items:
        prompt = ANALYSIS_PROMPT.format(
            content=item["content"][:3000],
            source_type=item["source_type"],
            influencer=item["influencer"],
            stages=", ".join(DEAL_STAGES),
        )
        requests.append(
            {
                "custom_id": item["id"],
                "params": {
                    "model": CLAUDE_MODEL,
                    "max_tokens": CLAUDE_MAX_TOKENS,
                    "temperature": CLAUDE_TEMPERATURE,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
        )
    return requests


def process_all_content() -> Optional[dict[str, Any]]:
    """Main processing function using Batch API."""
    logger.info("Starting content processing (Batch API + Haiku)...")

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set in environment")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Load existing processed data to merge with
    existing_processed, seen_ids = load_existing_processed()

    content_items = load_collected_content()

    if not content_items:
        logger.warning("No content to process")
        return

    # Filter out already processed items
    new_items = [item for item in content_items if item["id"] not in seen_ids]

    if not new_items:
        logger.info("All content already processed, nothing new to do")
        return

    logger.info(
        f"Found {len(new_items)} new items to process (skipping {len(content_items) - len(new_items)} already done)"
    )

    # Estimate cost (Haiku Batch: input $0.04/MTok, output $0.20/MTok)
    total_chars = sum(len(item["content"]) for item in new_items)
    estimated_input_tokens = total_chars // 4
    estimated_output_tokens = len(new_items) * 300
    estimated_cost = (estimated_input_tokens * 0.04 + estimated_output_tokens * 0.20) / 1_000_000
    logger.info(
        f"Estimated cost: ${estimated_cost:.2f} "
        f"(~{estimated_input_tokens:,} input + ~{estimated_output_tokens:,} output tokens, "
        f"Haiku Batch pricing)"
    )

    # Build item lookup for result processing
    item_lookup = {item["id"]: item for item in new_items}

    # Build and submit batch
    batch_requests = build_batch_requests(new_items)
    logger.info(f"Submitting batch of {len(batch_requests)} requests...")

    batch = client.messages.batches.create(requests=batch_requests)
    logger.info(f"Batch created: {batch.id} (status: {batch.processing_status})")

    # Poll for completion
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        logger.info(
            f"Batch {batch.id}: {batch.processing_status} "
            f"({done}/{total} done, {counts.succeeded} succeeded, {counts.errored} errored)"
        )
        if batch.processing_status == "ended":
            break
        time.sleep(POLL_INTERVAL)

    # Process results
    logger.info("Batch complete, processing results...")
    processed = list(existing_processed)
    new_included = 0
    skipped = 0
    errors = 0

    for entry in client.messages.batches.results(batch.id):
        custom_id = entry.custom_id
        item = item_lookup.get(custom_id)
        if not item:
            continue

        if entry.result.type != "succeeded":
            errors += 1
            logger.warning(f"Failed: {custom_id} ({entry.result.type})")
            continue

        try:
            response_text = entry.result.message.content[0].text.strip()
            # Strip markdown code fences if present
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]  # remove ```json line
                response_text = response_text.rsplit("```", 1)[0]  # remove closing ```
            analysis = json.loads(response_text)

            result = {
                "source_id": item["id"],
                "influencer": item["influencer"],
                "source_type": item["source_type"],
                "source_url": item["source_url"],
                "date_collected": item["date_collected"],
                **analysis,
            }

            if result.get("relevance_score", 0) >= RELEVANCE_THRESHOLD:
                processed.append(result)
                new_included += 1
            else:
                skipped += 1

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            errors += 1
            logger.warning(f"Parse error for {custom_id}: {e}")

    # Save merged results
    output = {
        "processed": processed,
        "processing_date": datetime.now().isoformat(),
        "total_processed": len(processed),
        "new_included": new_included,
        "skipped": skipped,
        "errors": errors,
        "existing_preserved": len(existing_processed),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(
        f"Processing complete: {new_included} new included, {skipped} skipped, "
        f"{errors} errors, {len(existing_processed)} preserved"
    )
    logger.info(f"Total records: {len(processed)}")
    logger.info(f"Output: {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    process_all_content()
