#!/usr/bin/env python3
"""
Airtable CSV Export

Generates CSV file from processed content for Airtable import.

Usage:
    python tools/export_airtable.py

Input:
    .tmp/processed_content.json

Output:
    outputs/sales_wisdom_YYYYMMDD.csv
"""
import csv
import json
import logging
from datetime import datetime

from config import (
    TMP_DIR,
    OUTPUTS_DIR,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# File paths
INPUT_FILE = TMP_DIR / "processed_content.json"

# CSV columns (match Airtable schema)
CSV_COLUMNS = [
    "Source ID",
    "Influencer",
    "Source Type",
    "Source URL",
    "Date Collected",
    "Primary Stage",
    "Secondary Stages",
    "Key Insight",
    "Tactical Steps",
    "Keywords",
    "Situation Examples",
    "Best Quote",
    "Relevance Score",
]


def format_list_field(items: list) -> str:
    """Format list as comma-separated string for Airtable multi-select."""
    if not items:
        return ""
    return ", ".join(str(item) for item in items)


def format_multiline_field(items: list) -> str:
    """Format list as newline-separated string for Airtable long text."""
    if not items:
        return ""
    return "\n".join(f"• {item}" for item in items)


def export_to_csv():
    """Main export function."""
    logger.info("Starting Airtable export...")

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.info("Run process_content.py first to generate processed content.")
        return

    with open(INPUT_FILE) as f:
        data = json.load(f)

    processed = data.get("processed", [])

    if not processed:
        logger.warning("No processed content to export")
        return

    # Generate output filename with date
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = OUTPUTS_DIR / f"sales_wisdom_{date_str}.csv"

    # Write CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for item in processed:
            row = {
                "Source ID": item.get("source_id", ""),
                "Influencer": item.get("influencer", ""),
                "Source Type": item.get("source_type", ""),
                "Source URL": item.get("source_url", ""),
                "Date Collected": item.get("date_collected", "")[:10],  # Date only
                "Primary Stage": item.get("primary_stage", ""),
                "Secondary Stages": format_list_field(item.get("secondary_stages", [])),
                "Key Insight": item.get("key_insight", ""),
                "Tactical Steps": format_multiline_field(item.get("tactical_steps", [])),
                "Keywords": format_list_field(item.get("keywords", [])),
                "Situation Examples": format_multiline_field(item.get("situation_examples", [])),
                "Best Quote": item.get("best_quote", ""),
                "Relevance Score": item.get("relevance_score", ""),
            }
            writer.writerow(row)

    logger.info(f"Exported {len(processed)} records to {output_file}")

    # Print summary
    print("\n" + "="*50)
    print("EXPORT SUMMARY")
    print("="*50)
    print(f"Records exported: {len(processed)}")
    print(f"Output file: {output_file}")
    print("\nNext steps:")
    print("1. Open Airtable and navigate to your base")
    print("2. Create new table or import to existing")
    print("3. File > Import > CSV")
    print("4. Map columns to correct field types:")
    print("   - Source Type, Primary Stage: Single Select")
    print("   - Secondary Stages, Keywords: Multi-select")
    print("   - Relevance Score: Number")
    print("   - All others: Text or Long Text")
    print("="*50)

    return output_file


if __name__ == "__main__":
    export_to_csv()
