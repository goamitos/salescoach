#!/usr/bin/env python3
"""
Content Processing with Claude API

Analyzes collected content, categorizes by deal stage,
and extracts structured insights.

Usage:
    python tools/process_content.py

Input:
    .tmp/linkedin_raw.json
    .tmp/youtube_raw.json

Output:
    .tmp/processed_content.json
"""
import json
import time
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from config import (
    TMP_DIR,
    ANTHROPIC_API_KEY,
    RATE_LIMIT_CLAUDE,
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
                content_items.append(
                    {
                        "id": f"li_{hash(post.get('url', ''))}",
                        "content": post.get("content", ""),
                        "influencer": post.get("influencer", "Unknown"),
                        "source_type": "linkedin",
                        "source_url": post.get("url", ""),
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


def analyze_content(client: anthropic.Anthropic, item: dict) -> dict | None:
    """Send content to Claude for analysis."""
    prompt = ANALYSIS_PROMPT.format(
        content=item["content"][:3000],  # Limit content length
        source_type=item["source_type"],
        influencer=item["influencer"],
        stages=", ".join(DEAL_STAGES),
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            temperature=CLAUDE_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON response
        response_text = response.content[0].text
        analysis = json.loads(response_text)

        return {
            "source_id": item["id"],
            "influencer": item["influencer"],
            "source_type": item["source_type"],
            "source_url": item["source_url"],
            "date_collected": item["date_collected"],
            **analysis,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse response for {item['id']}: {e}")
        return None

    except Exception as e:
        logger.error(f"API error for {item['id']}: {e}")
        return None


def load_existing_processed() -> tuple[list[dict], set[str]]:
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


def process_all_content():
    """Main processing function."""
    logger.info("Starting content processing...")

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

    # Estimate cost
    total_chars = sum(len(item["content"]) for item in new_items)
    estimated_tokens = total_chars // 4
    logger.info(
        f"Processing {len(new_items)} items (~{estimated_tokens:,} input tokens)"
    )

    processed = list(existing_processed)  # Start with existing data
    new_included = 0
    skipped = 0

    for i, item in enumerate(new_items):
        logger.info(f"Processing {i+1}/{len(new_items)}: {item['id']}")

        result = analyze_content(client, item)

        if result:
            if result.get("relevance_score", 0) >= RELEVANCE_THRESHOLD:
                processed.append(result)
                new_included += 1
                logger.info(f"  -> Score: {result.get('relevance_score')} (included)")
            else:
                skipped += 1
                logger.info(f"  -> Score: {result.get('relevance_score')} (skipped)")

        time.sleep(RATE_LIMIT_CLAUDE)

    # Save merged results
    output = {
        "processed": processed,
        "processing_date": datetime.now().isoformat(),
        "total_processed": len(processed),
        "new_included": new_included,
        "skipped": skipped,
        "existing_preserved": len(existing_processed),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(
        f"Processing complete: {new_included} new included, {skipped} skipped, {len(existing_processed)} preserved"
    )
    logger.info(f"Total records: {len(processed)}")
    logger.info(f"Output: {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    process_all_content()
