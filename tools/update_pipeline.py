#!/usr/bin/env python3
"""
Automated Pipeline Update

Fetches new videos from YouTube channel RSS feeds,
processes them with Claude, and pushes to Airtable.

Usage:
    python tools/update_pipeline.py

Features:
    - Discovers new videos from target channels via RSS (free, no API key)
    - Skips videos already in Airtable
    - Runs full pipeline: collect → process → push
"""
import json
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Add parent to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from pyairtable import Api

from config import (
    TMP_DIR,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# YouTube Channel IDs for RSS feeds
# Format: (channel_id, influencer_name)
TARGET_CHANNELS = [
    # Top LinkedIn Sales Voices
    ("UCKwbDwBK_adh4AgzprZb5FQ", "Ian Koniak"),  # Ian Koniak Sales Coaching
    ("UC5dUIRNBMfKND8w8MtcsFsA", "30MPC"),  # 30 Minutes to President's Club
    ("UCHLjEOsdrKQna86DToBSUkw", "Samantha McKenna"),  # #samsales
    ("UCOnSLryHal-I5SFokPIuUyQ", "Morgan Ingram"),  # The SDR Chronicles
    # Additional Influencers
    ("UCCGGmhqLy9bryNg-XlVi7Lg", "John Barrows"),  # JBarrows Sales Training
    ("UCBGpNArVNpXSWFnp4zbemig", "Josh Braun"),  # Josh Braun
    ("UC4RykET1R_18qDXfSUqhrUg", "Jeb Blount"),  # Sales Gravy
    ("UCsT0YIqwnpJCM-mx7-gSA4Q", "Gong.io"),  # Gong
]

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


def get_existing_video_urls() -> set:
    """Fetch existing video URLs from Airtable."""
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        logger.warning("Airtable not configured, skipping deduplication")
        return set()

    try:
        base_id = AIRTABLE_BASE_ID.split("/")[0]
        api = Api(AIRTABLE_API_KEY)
        table = api.table(base_id, AIRTABLE_TABLE_NAME)
        records = table.all()

        urls = {record["fields"].get("Source URL", "") for record in records}
        logger.info(f"Found {len(urls)} existing videos in Airtable")
        return urls

    except Exception as e:
        logger.error(f"Error fetching Airtable records: {e}")
        return set()


def fetch_channel_videos(channel_id: str, influencer: str) -> list[dict]:
    """Fetch recent videos from a YouTube channel RSS feed."""
    url = RSS_URL_TEMPLATE.format(channel_id)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Namespace for YouTube RSS
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }

        videos = []
        for entry in root.findall("atom:entry", ns):
            video_id = entry.find("yt:videoId", ns).text
            title = entry.find("atom:title", ns).text
            published = entry.find("atom:published", ns).text

            videos.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "published": published,
                    "influencer": influencer,
                    "channel_id": channel_id,
                    "url": f"https://youtube.com/watch?v={video_id}",
                }
            )

        return videos

    except Exception as e:
        logger.error(f"Error fetching RSS for {influencer}: {e}")
        return []


def discover_new_videos(existing_urls: set) -> list[tuple]:
    """Discover new videos from all target channels."""
    new_videos = []

    for channel_id, influencer in TARGET_CHANNELS:
        logger.info(f"Checking {influencer}...")
        videos = fetch_channel_videos(channel_id, influencer)

        for video in videos:
            if video["url"] not in existing_urls:
                new_videos.append(
                    (
                        video["video_id"],
                        video["influencer"],
                        f"{video['influencer']} Channel",
                    )
                )
                logger.info(f"  NEW: {video['title'][:50]}...")

    return new_videos


def update_collect_youtube(new_videos: list[tuple]):
    """Add new videos to collect_youtube.py TARGET_VIDEOS list."""
    collect_file = Path(__file__).parent / "collect_youtube.py"

    with open(collect_file, "r") as f:
        content = f.read()

    # Find the end of TARGET_VIDEOS list
    insert_marker = "]\n\nOUTPUT_FILE"

    if insert_marker not in content:
        logger.error("Could not find insertion point in collect_youtube.py")
        return False

    # Format new entries
    new_entries = (
        "\n    # Auto-discovered " + datetime.now().strftime("%Y-%m-%d") + "\n"
    )
    for video_id, influencer, channel in new_videos:
        new_entries += f'    ("{video_id}", "{influencer}", "{channel}"),\n'

    # Insert before closing bracket
    content = content.replace(insert_marker, new_entries + insert_marker)

    with open(collect_file, "w") as f:
        f.write(content)

    logger.info(f"Added {len(new_videos)} new videos to collect_youtube.py")
    return True


def run_pipeline():
    """Run the full collection, processing, and push pipeline."""
    import subprocess
    import sys

    tools_dir = Path(__file__).parent

    steps = [
        ("Collecting transcripts", [sys.executable, tools_dir / "collect_youtube.py"]),
        ("Processing with Claude", [sys.executable, tools_dir / "process_content.py"]),
        ("Pushing to Airtable", [sys.executable, tools_dir / "push_airtable.py"]),
    ]

    for step_name, cmd in steps:
        logger.info(f"\n{'='*50}")
        logger.info(f"STEP: {step_name}")
        logger.info(f"{'='*50}")

        result = subprocess.run(cmd, cwd=tools_dir.parent)

        if result.returncode != 0:
            logger.error(f"Step failed: {step_name}")
            return False

    return True


def main():
    """Main update function."""
    print("\n" + "=" * 60)
    print("SALES COACH PIPELINE UPDATE")
    print("=" * 60 + "\n")

    # Step 1: Get existing videos from Airtable
    logger.info("Checking existing videos in Airtable...")
    existing_urls = get_existing_video_urls()

    # Step 2: Discover new videos from RSS feeds
    logger.info("\nDiscovering new videos from YouTube channels...")
    new_videos = discover_new_videos(existing_urls)

    if not new_videos:
        print("\n" + "=" * 60)
        print("No new videos found. Your database is up to date!")
        print("=" * 60)
        return

    print(f"\nFound {len(new_videos)} new videos:")
    for video_id, influencer, _ in new_videos:
        print(f"  - {influencer}: {video_id}")

    # Step 3: Update collect_youtube.py with new videos
    logger.info("\nUpdating video list...")
    if not update_collect_youtube(new_videos):
        return

    # Step 4: Run the pipeline
    print("\n" + "=" * 60)
    print("Running pipeline for new videos...")
    print("=" * 60)

    if run_pipeline():
        print("\n" + "=" * 60)
        print("UPDATE COMPLETE!")
        print(f"Added {len(new_videos)} new videos to your Sales Coach database.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("UPDATE FAILED - Check logs above for errors")
        print("=" * 60)


if __name__ == "__main__":
    main()
