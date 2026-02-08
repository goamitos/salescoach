#!/usr/bin/env python3
"""
One-time migration of insights from Airtable to SQLite.

Pulls all records from the Airtable "Sales Wisdom" table and inserts them
into the local SQLite database with field mapping and format conversion.

Usage:
    python migrate_to_sqlite.py           # Full migration
    python migrate_to_sqlite.py --dry-run # Preview without writing

Input:
    Airtable API (requires AIRTABLE_API_KEY, AIRTABLE_BASE_ID)

Output:
    Records inserted into data/sales_coach.db (insights + FTS5 index)
"""

import json
import logging
import re
import sys

from pyairtable import Api

from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME
from db import get_connection, init_db, upsert_insight, get_stats

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """Convert influencer name to slug: 'John Smith' -> 'john-smith'."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def parse_csv_field(value: str) -> list:
    """Parse comma-separated Airtable field to list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bullet_field(value: str) -> list:
    """Parse bullet-point Airtable long text to list.

    Handles both '• item' and plain 'item' formats.
    """
    if not value:
        return []
    lines = value.strip().split("\n")
    return [re.sub(r"^[•\-\*]\s*", "", line).strip() for line in lines if line.strip()]


def map_airtable_record(record: dict) -> dict:
    """Map an Airtable record to SQLite insights schema."""
    fields = record.get("fields", {})

    influencer = fields.get("Influencer", "Unknown")
    source_type_raw = fields.get("Source Type", "")
    source_type = source_type_raw.lower() if source_type_raw else "unknown"
    # Normalize Airtable values: "Youtube" -> "youtube", "LinkedIn" -> "linkedin"

    source_id = fields.get("Source ID", "")
    if not source_id:
        # Fallback: use Airtable record ID
        source_id = record.get("id", "")

    return {
        "id": source_id,
        "influencer_slug": slugify(influencer),
        "influencer_name": influencer,
        "source_type": source_type,
        "source_url": fields.get("Source URL", ""),
        "date_collected": fields.get("Date Collected", ""),
        "primary_stage": fields.get("Primary Stage", "General Sales Mindset"),
        "secondary_stages": parse_csv_field(fields.get("Secondary Stages", "")),
        "key_insight": fields.get("Key Insight", ""),
        "tactical_steps": parse_bullet_field(fields.get("Tactical Steps", "")),
        "keywords": parse_csv_field(fields.get("Keywords", "")),
        "situation_examples": parse_bullet_field(fields.get("Situation Examples", "")),
        "best_quote": fields.get("Best Quote", ""),
        "relevance_score": fields.get("Relevance Score", 0),
    }


def migrate() -> None:
    """Pull all Airtable records and insert into SQLite."""
    dry_run = "--dry-run" in sys.argv

    if not AIRTABLE_API_KEY:
        logger.error("AIRTABLE_API_KEY not set. Run via ./run.sh or set in .env")
        return
    if not AIRTABLE_BASE_ID:
        logger.error("AIRTABLE_BASE_ID not set")
        return

    # Connect to Airtable
    base_id = AIRTABLE_BASE_ID.split("/")[0]
    api = Api(AIRTABLE_API_KEY)
    table = api.table(base_id, AIRTABLE_TABLE_NAME)

    logger.info("Fetching all records from Airtable '%s'...", AIRTABLE_TABLE_NAME)
    records = table.all()
    logger.info("Fetched %d records from Airtable", len(records))

    if not records:
        logger.warning("No records found in Airtable")
        return

    if dry_run:
        # Preview first 3 records
        print("=" * 50)
        print("DRY RUN — Preview of first 3 records:")
        print("=" * 50)
        for r in records[:3]:
            mapped = map_airtable_record(r)
            print(json.dumps(mapped, indent=2)[:500])
            print("---")
        print(f"\nTotal records to migrate: {len(records)}")
        return

    # Initialize DB and insert
    init_db()
    conn = get_connection()

    try:
        migrated = 0
        skipped = 0

        for record in records:
            mapped = map_airtable_record(record)

            if not mapped["key_insight"]:
                logger.debug("Skipping record with empty key_insight: %s", mapped["id"])
                skipped += 1
                continue

            upsert_insight(conn, mapped)
            migrated += 1

        conn.commit()

        stats = get_stats(conn)
        print("=" * 50)
        print("AIRTABLE → SQLITE MIGRATION COMPLETE")
        print("=" * 50)
        print(f"  Records migrated: {migrated}")
        print(f"  Records skipped:  {skipped}")
        print(f"  DB insights total: {stats['insights']}")
        print(f"  DB file: {conn.execute('PRAGMA page_count').fetchone()[0] * conn.execute('PRAGMA page_size').fetchone()[0] / 1024:.0f} KB")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
