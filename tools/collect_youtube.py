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
import os
import time
import logging
from datetime import datetime
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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

# YouTube Channels Reference — Validated via YouTube Data API v3 (2026-02-06)
# ===========================================================================
# Format: Expert Name: "Channel Name" (topic) | or "Guest appearances only"
# Channels verified by matching API channel search → uploads playlist → sales content.
#
# VERIFIED OWN CHANNELS (29 experts)
# -----------------------------------
# Ian Koniak:          "Ian Koniak Sales Coaching" (enterprise sales, discovery)
# Morgan J Ingram:     "Morgan J Ingram" / "The SDR Chronicles" (SDR, outbound)
# Daniel Disney:       "Daniel Disney" (LinkedIn selling)
# Samantha McKenna:    "Samantha McKenna - #samsales" (Show Me You Know Me)
# John Barrows:        "John Barrows" / "JBarrows Sales Training" (sales training)
# Josh Braun:          "Josh Braun" (outbound, objection handling)
# Jeb Blount:          "Sales Gravy" (sales acceleration, EQ)
# Chris Voss:          "Chris Voss & The Black Swan Group" (negotiation)
# Will Aitken:         "Will Aitken" (sales leadership, coaching)
# Devin Reed:          "Devin Reed | The Reeder" (content, copywriting)
# Florin Tatulea:      "Florin Tatulea" (LinkedIn selling, SDR)
# Kyle Coleman:        "Kyle Coleman" (messaging, GTM)
# Anthony Iannarino:   "Anthony Iannarino" (B2B sales leadership)
# Chris Orlob:         "Chris Orlob at pclub" (deal mechanics, data-driven)
# Jill Konrath:        "Jill Konrath" (SNAP selling, agile selling)
# Shari Levitin:       "Shari Levitin" (human-centered selling)
# Tiffani Bova:        "Tiffani Bova" (growth strategy, keynotes)
# Amy Volas:           "Amy Volas Avenue Talent Partners" (GTM hiring)
# Jim Keenan:          "Keenan" (Gap Selling)
# Mark Hunter:         "Mark Hunter" (prospecting, The Sales Hunter)
# Kwame Christian:     "Kwame Christian Esq., M.A." (difficult conversations)
# Mo Bunnell:          "Mo Bunnell" (business development)
# Scott Leese:         "The Scott Leese" (Surf & Sales, pipeline scaling)
# Hannah Ajikawo:      "by Hannah Ajikawo" (GTM, EMEA sales)
# Colin Specter:       "Colin Specter" (AI cold calling, Orum)
# Giulio Segantini:    "Giulio Segantini" (Underdog Sales, cold calling)
# Nick Cegelski:       "Nick Cegelski" (30MPC co-host, cold calling)
# Sarah Brazier:       "Sarah Brazier" (SDR strategy)
# Niraj Kapur:         "Neeraj Kapur" (trust building, LinkedIn)
#
# COMPANY CHANNELS (3)
# --------------------
# 30MPC:               "30 Minutes to President's Club" (cold calling, discovery)
# Gong.io:             "Gong" (revenue intelligence, data-driven sales)
# Pavilion:            No curated videos yet
#
# GUEST APPEARANCES ONLY (13 experts — no verified own channel)
# --------------------------------------------------------------
# Nate Nasralla:       Guest on 30MPC, pclub, Sales Feed (discovery, qualification)
# Armand Farrokh:      Guest on 30MPC, Pipedrive, Josh Braun (discovery, frameworks)
# Gal Aga:             Guest on Project Moneyball, Steve Pugh (Aligned, buyer enablement)
# Becc Holland:        Guest on Chili Piper, Chorus (Flip the Script, personalization)
# Jen Allen-Knuth:     Guest on Close, Heinz Marketing, Lavender (enterprise discovery)
# Belal Batrawy:       Guest on Drift, Mixmax, Sales Feed (Death to Fluff, outreach)
# Rosalyn Santa Elena: Guest on SaaStr, Salesloft, Ebsta (RevOps)
# Bryan Tucker:        Guest on Ambition (sales leadership)
# Kevin Dorsey:        Guest on Inside Sales Excellence, RevGenius, SaaStock (KD, leadership)
# Mark Kosoglow:       Guest on Emblaze, Sell Better (sales leadership)
# Maria Bross:         Guest on Sales Stories IRL, Sell Better (sales strategy)
# Jesse Gittler:       Guest on Sales Leader Forums (sales leadership)
# Julie Hansen:        Guest on Crystal Knows, Heinz Marketing (virtual selling)
#
# GUEST APPEARANCES (added via targeted search, 2026-02-07)
# ----------------------------------------------------------
# Alexandra Carter:    Negotiation expert — CNBC, Google, BigSpeak, Banking On Cultura (15 videos)
# Chantel George:      Sistas in Sales channel (@sistasinsales) — summit workshops, panels (15 videos)
# Justin Michael:      JMM/HYPCCCYCL — FunnelFLARE, Oren Klaff, RightBound, Apollo.io (7 videos)
#
# NO USABLE YOUTUBE CONTENT (3 experts)
# --------------------------------------
# Ron Kimhi:           No YouTube presence found
# Caroline Celis:      Only 1 Repvue appearance (too obscure to surface)
# Erica Franklin:      Appears in Sistas in Sales panels but not named in titles

# Target video IDs — loaded from data/target_videos.json (curated subset)
# Format: (video_id, influencer_name, channel_name)
def _load_target_videos():
    """Load curated target videos from data/target_videos.json."""
    import json
    from config import PROJECT_ROOT

    target_path = PROJECT_ROOT / "data" / "target_videos.json"
    with open(target_path) as f:
        data = json.load(f)
    return [
        (v["video_id"], v["influencer"], v["channel"])
        for v in data["videos"]
    ]


TARGET_VIDEOS = _load_target_videos()

OUTPUT_FILE = TMP_DIR / "youtube_raw.json"
ERROR_LOG = TMP_DIR / "youtube_errors.log"

# Chunking settings
CHUNK_SIZE = 500  # words
CHUNK_OVERLAP = 50  # words


def get_existing_video_urls() -> set[str]:
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
) -> list[dict[str, any]]:
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


_proxy_url = os.environ.get("DECODO_PROXY_URL")
if _proxy_url:
    logger.info("Decodo residential proxy enabled")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _fetch_transcript(video_id: str) -> list[any]:
    """Fetch transcript via proxy (new connection per request for IP rotation)."""
    if _proxy_url:
        api = YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=_proxy_url,
                https_url=_proxy_url,
            )
        )
    else:
        api = YouTubeTranscriptApi()
    return api.fetch(video_id)


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video."""
    try:
        transcript_list = _fetch_transcript(video_id)
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


def collect_transcripts() -> dict[str, any]:
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
