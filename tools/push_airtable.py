#!/usr/bin/env python3
"""
Airtable & SQLite Push

Pushes processed content to both Airtable (via API) and SQLite (local DB).
Handles deduplication by Source ID.

Usage:
    python tools/push_airtable.py

Input:
    .tmp/processed_content.json

Output:
    Records created/updated in Airtable and SQLite
"""
import json
import logging
import re
import time
from typing import Optional
from pyairtable import Api
from pyairtable.formulas import match

from config import (
    TMP_DIR,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    DEAL_STAGES,
)
from db import get_connection, init_db, upsert_insight

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# File paths
INPUT_FILE = TMP_DIR / "processed_content.json"


# Stages that exist as Airtable single-select options (subset of DEAL_STAGES)
AIRTABLE_STAGES = {
    "Account Research", "Business Case Development", "Demo & Presentation",
    "Discovery", "General Sales Mindset", "Initial Contact", "Needs Analysis",
    "Outreach Strategy", "Procurement & Negotiation", "Stakeholder Mapping",
    "Territory Planning",
}

# Map valid deal stages that don't exist in Airtable to closest match
STAGE_REMAP = {
    "Closing": "Procurement & Negotiation",
    "Onboarding & Expansion": "General Sales Mindset",
    "Proof of Value": "Business Case Development",
    "RFP/RFQ Response": "Procurement & Negotiation",
}


def sanitize_stage(stage: str) -> str:
    """Map stage name to an Airtable-compatible option."""
    if stage in AIRTABLE_STAGES:
        return stage
    return STAGE_REMAP.get(stage, "General Sales Mindset")


def format_list_field(items: Optional[list[str]]) -> str:
    """Format list as comma-separated string for Airtable multi-select."""
    if not items:
        return ""
    return ", ".join(str(item) for item in items)


def format_multiline_field(items: Optional[list[str]]) -> str:
    """Format list as newline-separated string for Airtable long text."""
    if not items:
        return ""
    return "\n".join(f"• {item}" for item in items)


def push_to_airtable() -> None:
    """Push processed content to Airtable via API."""
    logger.info("Starting Airtable push...")

    # Validate config
    if not AIRTABLE_API_KEY:
        logger.error("AIRTABLE_API_KEY not set in environment")
        return

    if not AIRTABLE_BASE_ID:
        logger.error("AIRTABLE_BASE_ID not set in environment")
        return

    # Load processed content
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.info("Run process_content.py first to generate processed content.")
        return

    with open(INPUT_FILE) as f:
        data = json.load(f)

    processed = data.get("processed", [])

    if not processed:
        logger.warning("No processed content to push")
        return

    # Parse base ID (may contain table/view IDs)
    base_id = AIRTABLE_BASE_ID.split("/")[0]

    # Connect to Airtable
    api = Api(AIRTABLE_API_KEY)
    table = api.table(base_id, AIRTABLE_TABLE_NAME)

    # Get existing records for deduplication (by Source ID, not URL)
    # Multiple insights can come from same URL (e.g., YouTube video chunks)
    logger.info("Fetching existing records for deduplication...")
    existing_records = table.all()
    existing_ids = {
        record["fields"].get("Source ID"): record["id"]
        for record in existing_records
        if record["fields"].get("Source ID")
    }
    logger.info(f"Found {len(existing_ids)} existing records")

    # Prepare records
    created = 0
    updated = 0
    errors = 0
    failed_ids: list[str] = []

    # Process in batches of 10 to avoid rate limits
    BATCH_SIZE = 10
    BATCH_DELAY = 1.0  # seconds between batches

    for batch_start in range(0, len(processed), BATCH_SIZE):
        batch = processed[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(processed) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} records)")

        for item in batch:
            source_id = item.get("source_id", "")
            source_url = item.get("source_url", "")

            # Map source type to match Airtable options exactly
            source_type_map = {"youtube": "Youtube", "linkedin": "LinkedIn"}
            source_type_raw = item.get("source_type", "")
            source_type = source_type_map.get(source_type_raw, source_type_raw)

            record_data = {
                "Source ID": source_id,
                "Influencer": item.get("influencer", ""),
                "Source Type": source_type,
                "Source URL": source_url,
                "Date Collected": item.get("date_collected", "")[:10],
                "Primary Stage": sanitize_stage(item.get("primary_stage", "")),
                "Secondary Stages": format_list_field(
                    [sanitize_stage(s) for s in item.get("secondary_stages", [])]
                ),
                "Key Insight": item.get("key_insight", ""),
                "Tactical Steps": format_multiline_field(item.get("tactical_steps", [])),
                "Keywords": format_list_field(item.get("keywords", [])),
                "Situation Examples": format_multiline_field(
                    item.get("situation_examples", [])
                ),
                "Best Quote": item.get("best_quote", ""),
                "Relevance Score": item.get("relevance_score", 0),
            }

            try:
                if source_id in existing_ids:
                    # Update existing record
                    record_id = existing_ids[source_id]
                    table.update(record_id, record_data)
                    updated += 1
                    logger.debug(f"Updated: {source_id}")
                else:
                    # Create new record
                    table.create(record_data)
                    created += 1
                    logger.debug(f"Created: {source_id}")

            except Exception as e:
                logger.error(f"Error pushing record {source_url[:50]}: {e}")
                errors += 1
                failed_ids.append(source_id)

        # Delay between batches to respect rate limits
        if batch_start + BATCH_SIZE < len(processed):
            time.sleep(BATCH_DELAY)

    # Summary
    print("\n" + "=" * 50)
    print("AIRTABLE PUSH SUMMARY")
    print("=" * 50)
    print(f"Records created: {created}")
    print(f"Records updated: {updated}")
    print(f"Errors: {errors}")
    print(f"Total processed: {len(processed)}")
    if failed_ids:
        print(f"Failed IDs: {', '.join(failed_ids[:10])}" + ("..." if len(failed_ids) > 10 else ""))
    print("=" * 50)

    logger.info(f"Push complete: {created} created, {updated} updated, {errors} errors")


def _slugify(name: str) -> str:
    """Convert influencer name to slug: 'John Smith' -> 'john-smith'."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def push_to_sqlite() -> None:
    """Push processed content to SQLite database (dual-write alongside Airtable)."""
    logger.info("Starting SQLite push...")

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE) as f:
        data = json.load(f)

    processed = data.get("processed", [])
    if not processed:
        logger.warning("No processed content to push to SQLite")
        return

    init_db()
    conn = get_connection()

    try:
        pushed = 0
        errors = 0

        for item in processed:
            try:
                influencer = item.get("influencer", "Unknown")
                upsert_insight(conn, {
                    "id": item.get("source_id", ""),
                    "influencer_slug": _slugify(influencer),
                    "influencer_name": influencer,
                    "source_type": item.get("source_type", ""),
                    "source_url": item.get("source_url", ""),
                    "date_collected": item.get("date_collected", "")[:10],
                    "primary_stage": item.get("primary_stage", "General Sales Mindset"),
                    "secondary_stages": item.get("secondary_stages", []),
                    "key_insight": item.get("key_insight", ""),
                    "tactical_steps": item.get("tactical_steps", []),
                    "keywords": item.get("keywords", []),
                    "situation_examples": item.get("situation_examples", []),
                    "best_quote": item.get("best_quote", ""),
                    "relevance_score": item.get("relevance_score", 0),
                })
                pushed += 1
            except Exception as e:
                logger.error(f"SQLite error for {item.get('source_id', '?')}: {e}")
                errors += 1

        conn.commit()

        print("\n" + "=" * 50)
        print("SQLITE PUSH SUMMARY")
        print("=" * 50)
        print(f"Records upserted: {pushed}")
        print(f"Errors: {errors}")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == "__main__":
    push_to_airtable()
    push_to_sqlite()
