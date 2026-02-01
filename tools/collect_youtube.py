#!/usr/bin/env python3
"""
YouTube Transcript Collection

Extracts transcripts from sales-focused YouTube videos
for processing and categorization.

Usage:
    python tools/collect_youtube.py

Output:
    .tmp/youtube_raw.json
"""
import json
import time
import logging
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
)

from pyairtable import Api

from config import (
    TMP_DIR,
    RATE_LIMIT_YOUTUBE,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# YouTube Channels Reference (for manual video discovery)
# =====================================================
# TOP 12 LINKEDIN SALES VOICES
# =====================================================
# 1. Ian Koniak: youtube.com/channel/UCKwbDwBK_adh4AgzprZb5FQ (enterprise sales, discovery)
# 2. Nate Nasralla: No dedicated channel (discovery questions, qualification)
# 3. Morgan Ingram: The SDR Chronicles (SDR, outbound, sequences)
# 4. Armand Farrokh: youtube.com/@30MPC (30MPC, discovery)
# 5. Nick Cegelski: youtube.com/@30MPC (30MPC, cold calling)
# 6. Will Aitken: Various appearances (sales leadership, coaching)
# 7. Devin Reed: Various appearances (content, copywriting)
# 8. Florin Tatulea: No dedicated channel (LinkedIn selling)
# 9. Kyle Coleman: Various appearances (messaging, GTM)
# 10. Daniel Disney: youtube.com/@DanielDisney (LinkedIn selling)
# 11. Samantha McKenna: youtube.com/channel/UCHLjEOsdrKQna86DToBSUkw (#samsales, Show Me You Know Me)
# 12. Gal Aga: Various appearances (Aligned, buyer enablement)
#
# ADDITIONAL INFLUENCERS
# - John Barrows: youtube.com/@JBarrowsSalesTraining
# - Josh Braun: youtube.com/@JoshBraun
# - Jeb Blount: youtube.com/@SalesGravy
# - Chris Voss: various (MasterClass, Big Think)
# - Gong.io: youtube.com/@Gong

# Target video IDs (curated list)
# Format: (video_id, influencer, channel)
TARGET_VIDEOS = [
    # =====================================================
    # TOP 12 LINKEDIN SALES VOICES (from plan.md)
    # =====================================================
    # 1. Ian Koniak - Enterprise sales, discovery (Popular videos)
    (
        "f3pTqJ9yARU",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # FREE TRAINING: MAKE $500K-1M/YEAR
    (
        "XUkgyemEbc0",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How I became #1 Enterprise AE at Salesforce
    (
        "MufIRTnXz1Y",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How to Use Chat GPT for e-mail Prospecting
    (
        "faFJ13Mdd3E",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # The Science of Selling: quota 42 months
    (
        "Mefkm3F3BeU",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How to Build an Effective Prospecting Sequence
    # 3. Morgan J Ingram - SDR, outbound, sequences
    ("q0x1g0QFcFk", "Morgan Ingram", "The SDR Chronicles"),
    ("hTJi7pE9CVY", "Morgan Ingram", "The SDR Chronicles"),
    # 4 & 5. Armand Farrokh & Nick Cegelski - 30MPC
    (
        "5pjUStm0pvo",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Sales Email Elimination: 5 Cold Emails
    ("XvuWnvR0Mpc", "30MPC", "30 Minutes to President's Club"),  # The $1M Negotiation
    (
        "2vivv2HeiBU",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Cold Call Masterclass: The Perfect Script
    ("r43V0YXGLhg", "30MPC", "30 Minutes to President's Club"),  # Cold Call 3v3
    ("Ag-6pB51s5o", "30MPC", "30 Minutes to President's Club"),  # Cold Email Showdown
    (
        "foeXnJ1b0UE",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # The $30M Deal Sold With One Page
    ("w1_0co11VWk", "30MPC", "30 Minutes to President's Club"),  # #1 Sales Rep Demo
    (
        "f-P8e2VSUnk",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Negotiation Masterclass
    ("9WtOHUDgbIA", "30MPC", "30 Minutes to President's Club"),  # Live Cold Calls
    # 11. Samantha McKenna - #samsales, Show Me You Know Me
    ("h2872iUIXm4", "Samantha McKenna", "#samsales"),  # LinkedIn Algo Hacks
    (
        "2K3Hddd3jkw",
        "Samantha McKenna",
        "#samsales",
    ),  # Show Me You Know Me - Subject Lines
    (
        "fz9Z_4PDLOQ",
        "Samantha McKenna",
        "#samsales",
    ),  # From Cooked to Booked w/ Morgan Ingram
    ("S8g0nD-LARM", "Samantha McKenna", "#samsales"),  # Why the effort matters - SMYKM
    (
        "9XvRJagw6ZA",
        "Samantha McKenna",
        "#samsales",
    ),  # How to Break into an ENT Account
    # =====================================================
    # ADDITIONAL INFLUENCERS
    # =====================================================
    # John Barrows - JBarrows Sales Training
    ("Z5vxRC8dMvs", "John Barrows", "JBarrows Sales Training"),
    ("gOqL9-RCj94", "John Barrows", "JBarrows Sales Training"),
    # Josh Braun - Sales tips
    ("j5zRyXLvngg", "Josh Braun", "Josh Braun"),
    ("Kl2zmeHblmI", "Josh Braun", "Josh Braun"),
    # Jeb Blount - Sales Gravy
    ("n6mNxKAt9TU", "Jeb Blount", "Sales Gravy"),
    ("3y8nP8VnOp0", "Jeb Blount", "Sales Gravy"),
    # Chris Voss - Negotiation
    ("guZa7mQV1l0", "Chris Voss", "MasterClass"),
    ("llctqNJr2IU", "Chris Voss", "Big Think"),
    # Gong.io - Data-driven sales
    ("SHwGqFt3fkU", "Gong.io", "Gong"),
    ("tXrU8-S-F6U", "Gong.io", "Gong"),
    # Auto-discovered 2026-01-31
    ("K9ffRCbkrRc", "Ian Koniak", "Ian Koniak Channel"),
    ("_G-5i4HeO0Y", "Ian Koniak", "Ian Koniak Channel"),
    ("PwPriX_cmVo", "Ian Koniak", "Ian Koniak Channel"),
    ("2FRu6gXfXvM", "Ian Koniak", "Ian Koniak Channel"),
    ("inPr-Hxe_4k", "Ian Koniak", "Ian Koniak Channel"),
    ("iQKYPZE9MKk", "Ian Koniak", "Ian Koniak Channel"),
    ("FN8zG1Xm8OQ", "Ian Koniak", "Ian Koniak Channel"),
    ("US4va6fXUUo", "Ian Koniak", "Ian Koniak Channel"),
    ("e36YdbEyOb4", "Ian Koniak", "Ian Koniak Channel"),
    ("9sHMs3s-jRk", "Ian Koniak", "Ian Koniak Channel"),
    ("qxWI06O1Mr4", "Ian Koniak", "Ian Koniak Channel"),
    ("FjDfipbnd1Y", "Ian Koniak", "Ian Koniak Channel"),
    ("15pdWDG5eaw", "Ian Koniak", "Ian Koniak Channel"),
    ("uqTCYF53dUg", "Ian Koniak", "Ian Koniak Channel"),
    ("-BYCegr0tiQ", "Ian Koniak", "Ian Koniak Channel"),
    ("KNtpGkD_Mkw", "Samantha McKenna", "Samantha McKenna Channel"),
    ("AFL9_niYyok", "Samantha McKenna", "Samantha McKenna Channel"),
    ("VXg15KLlKO8", "Samantha McKenna", "Samantha McKenna Channel"),
    ("o_uDR792gKk", "Samantha McKenna", "Samantha McKenna Channel"),
    ("aQWpaLWOZIg", "Samantha McKenna", "Samantha McKenna Channel"),
    ("sqhtOhW0NbU", "Samantha McKenna", "Samantha McKenna Channel"),
    ("cDLzOXPM58k", "Samantha McKenna", "Samantha McKenna Channel"),
    ("_4ybWNKcGM4", "Samantha McKenna", "Samantha McKenna Channel"),
    ("rBNHyj0OdMg", "Samantha McKenna", "Samantha McKenna Channel"),
    ("EGi8nJgdXmA", "Samantha McKenna", "Samantha McKenna Channel"),
    ("Tr5Hs2ERej0", "Samantha McKenna", "Samantha McKenna Channel"),
    ("O7lrrp3S80c", "Samantha McKenna", "Samantha McKenna Channel"),
    ("V6MnoIYMeFE", "Samantha McKenna", "Samantha McKenna Channel"),
    ("-uP1HyZ2V80", "Samantha McKenna", "Samantha McKenna Channel"),
    ("s5Md43JBt-U", "Samantha McKenna", "Samantha McKenna Channel"),
    ("OCe4dtXlUKI", "Gong.io", "Gong.io Channel"),
    ("bVWJml2otH0", "Gong.io", "Gong.io Channel"),
    ("u2SOTGzL3xU", "Gong.io", "Gong.io Channel"),
    ("n_QMW-QD9dQ", "Gong.io", "Gong.io Channel"),
    ("tNB3pHLoaM0", "Gong.io", "Gong.io Channel"),
    ("MUMy99Ae2kE", "Gong.io", "Gong.io Channel"),
    ("s9ZaTt9gFD8", "Gong.io", "Gong.io Channel"),
    ("EcLtC5552rU", "Gong.io", "Gong.io Channel"),
    ("4en_TsXhtzY", "Gong.io", "Gong.io Channel"),
    ("zsgjOOsAlf8", "Gong.io", "Gong.io Channel"),
    ("6kzdhtglrRY", "Gong.io", "Gong.io Channel"),
    ("-Hpv3hqpG-c", "Gong.io", "Gong.io Channel"),
    ("XQGMeJf-Kmg", "Gong.io", "Gong.io Channel"),
    ("LnwiL2ymMgE", "Gong.io", "Gong.io Channel"),
    ("nL24YCoXw3Y", "Gong.io", "Gong.io Channel"),
]

OUTPUT_FILE = TMP_DIR / "youtube_raw.json"
ERROR_LOG = TMP_DIR / "youtube_errors.log"

# Chunking settings
CHUNK_SIZE = 500  # words
CHUNK_OVERLAP = 50  # words


def get_existing_video_urls() -> set:
    """Fetch existing video URLs from Airtable to skip re-processing."""
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_NAME:
        logger.info("Airtable not configured, processing all videos")
        return set()

    try:
        base_id = AIRTABLE_BASE_ID.split("/")[0]
        api = Api(AIRTABLE_API_KEY)
        table = api.table(base_id, AIRTABLE_TABLE_NAME)
        records = table.all()

        urls = {record["fields"].get("Source URL", "") for record in records}
        logger.info(f"Found {len(urls)} existing videos in Airtable (will skip)")
        return urls

    except Exception as e:
        logger.warning(f"Could not fetch Airtable records: {e}")
        logger.info("Processing all videos")
        return set()


def chunk_transcript(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Split transcript into overlapping chunks."""
    words = text.split()
    chunks = []

    if len(words) <= chunk_size:
        return [{"chunk_index": 0, "content": text, "start_word": 0}]

    start = 0
    chunk_index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]

        chunks.append(
            {
                "chunk_index": chunk_index,
                "content": " ".join(chunk_words),
                "start_word": start,
            }
        )

        chunk_index += 1
        start = end - overlap

        if start >= len(words) - overlap:
            break

    return chunks


def get_transcript(video_id: str) -> str | None:
    """Fetch transcript for a YouTube video."""
    try:
        # New API: instantiate class and call fetch()
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.fetch(video_id)
        full_text = " ".join([entry.text for entry in transcript_list])
        return full_text

    except TranscriptsDisabled:
        logger.warning(f"Transcripts disabled for {video_id}")
        return None

    except NoTranscriptFound:
        logger.warning(f"No transcript found for {video_id}")
        return None

    except Exception as e:
        logger.error(f"Error getting transcript for {video_id}: {e}")
        with open(ERROR_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {video_id} - {e}\n")
        return None


def collect_transcripts():
    """Main collection function."""
    logger.info("Starting YouTube transcript collection...")

    # Get existing videos to skip
    existing_urls = get_existing_video_urls()

    # Filter to only new videos
    videos_to_process = [
        (vid, inf, ch)
        for vid, inf, ch in TARGET_VIDEOS
        if f"https://youtube.com/watch?v={vid}" not in existing_urls
    ]

    if not videos_to_process:
        logger.info("No new videos to process")
        return {
            "videos": [],
            "collection_date": datetime.now().isoformat(),
            "video_count": 0,
        }

    logger.info(
        f"Processing {len(videos_to_process)} new videos (skipping {len(TARGET_VIDEOS) - len(videos_to_process)} existing)"
    )

    all_videos = []

    for video_id, influencer, channel in videos_to_process:
        logger.info(f"Processing: {video_id} ({influencer})")

        transcript = get_transcript(video_id)

        if transcript:
            chunks = chunk_transcript(transcript)

            video_data = {
                "video_id": video_id,
                "influencer": influencer,
                "channel": channel,
                "url": f"https://youtube.com/watch?v={video_id}",
                "transcript_chunks": chunks,
                "date_collected": datetime.now().isoformat(),
                "source_type": "youtube",
            }

            all_videos.append(video_data)
            logger.info(f"  -> {len(chunks)} chunks extracted")

        time.sleep(RATE_LIMIT_YOUTUBE)

    # Save results
    output = {
        "videos": all_videos,
        "collection_date": datetime.now().isoformat(),
        "video_count": len(all_videos),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Collected {len(all_videos)} videos -> {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    collect_transcripts()
