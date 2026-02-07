#!/usr/bin/env python3
"""
YouTube Video Curation via YouTube Data API v3

One-time discovery script that finds 5-15 relevant sales videos per expert.
Uses channel search + video search to discover both own-channel content
and guest appearances.

Usage:
    ./run.sh curate_youtube

Output:
    data/curated_videos.json
    Prints TARGET_VIDEOS-formatted tuples for collect_youtube.py

API Quota Budget (10,000 units/day):
    - Channel search: 48 experts × 100 units = 4,800
    - Video search: 48 experts × 100 units = 4,800
    - Playlist fetches: ~48 × 3 pages × 1 unit = ~144
    - Total: ~9,744 units
"""

import json
import time
import logging
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict

import requests

from config import YOUTUBE_API_KEY, PROJECT_ROOT

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
INFLUENCERS_FILE = PROJECT_ROOT / "data" / "influencers.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "curated_videos.json"

# API settings
API_BASE = "https://www.googleapis.com/youtube/v3"
RATE_LIMIT = 0.5  # seconds between API calls (generous)

# How many videos we want per expert
MIN_VIDEOS_PER_EXPERT = 5
MAX_VIDEOS_PER_EXPERT = 15

# Sales-related keywords for filtering video titles
SALES_KEYWORDS = [
    "sales", "selling", "sell", "cold call", "cold email", "prospect",
    "prospecting", "deal", "close", "closing", "negotiate", "negotiation",
    "pipeline", "sdr", "bdr", "ae", "b2b", "discovery", "demo",
    "revenue", "outbound", "inbound", "quota", "commission",
    "objection", "follow up", "follow-up", "buyer", "customer",
    "pitch", "pricing", "proposal", "contract", "enterprise",
    "saas", "aro", "arv", "mrr", "churn", "upsell", "cross-sell",
    "account executive", "business development", "gtm", "go-to-market",
    "linkedin", "email", "messaging", "stakeholder", "champion",
    "decision maker", "c-suite", "cfo", "ceo", "cro", "vp sales",
    "meddic", "meddicc", "bant", "spin", "challenger", "sandler",
    "gap selling", "value selling", "consultative",
    "coaching", "leadership", "enablement", "onboarding",
    "forecast", "funnel", "conversion", "win rate",
]

# Compile a single regex for fast matching
SALES_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in SALES_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Experts who are already covered in TARGET_VIDEOS — we still search for them
# but will deduplicate later
EXISTING_EXPERTS = {
    "Ian Koniak", "Morgan J Ingram", "30MPC", "Samantha McKenna",
    "John Barrows", "Josh Braun", "Jeb Blount", "Chris Voss", "Gong.io",
}

# Track API quota usage
quota_used = 0


def api_call(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API call with rate limiting and error handling."""
    global quota_used
    params["key"] = YOUTUBE_API_KEY

    url = f"{API_BASE}/{endpoint}"
    time.sleep(RATE_LIMIT)

    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code == 403:
        error_data = resp.json()
        reason = error_data.get("error", {}).get("errors", [{}])[0].get("reason", "")
        if reason == "quotaExceeded":
            logger.error("YouTube API quota exceeded! Saving partial results.")
            raise QuotaExceededError("Daily quota exceeded")
        logger.error(f"API 403 error: {error_data}")
        raise Exception(f"API error: {resp.status_code} - {resp.text[:200]}")

    resp.raise_for_status()
    return resp.json()


class QuotaExceededError(Exception):
    pass


def search_channel(expert_name: str) -> Optional[dict]:
    """Search for an expert's YouTube channel. Costs 100 quota units."""
    global quota_used
    quota_used += 100

    try:
        data = api_call("search", {
            "part": "snippet",
            "q": expert_name,
            "type": "channel",
            "maxResults": 5,
        })
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.warning(f"Channel search failed for {expert_name}: {e}")
        return None

    for item in data.get("items", []):
        title = item["snippet"]["title"].lower()
        name_parts = expert_name.lower().split()
        # Check if channel title contains the expert's name (at least last name)
        if any(part in title for part in name_parts if len(part) > 2):
            channel_id = item["snippet"]["channelId"]
            channel_title = item["snippet"]["title"]
            logger.info(f"  Found channel: {channel_title} ({channel_id})")
            return {"channel_id": channel_id, "channel_title": channel_title}

    logger.info(f"  No matching channel found for {expert_name}")
    return None


def get_uploads_playlist(channel_id: str) -> Optional[str]:
    """Get the uploads playlist ID for a channel. Costs 1 quota unit."""
    global quota_used
    quota_used += 1

    try:
        data = api_call("channels", {
            "part": "contentDetails",
            "id": channel_id,
        })
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.warning(f"Failed to get uploads playlist for {channel_id}: {e}")
        return None

    items = data.get("items", [])
    if items:
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    return None


def get_playlist_videos(playlist_id: str, max_pages: int = 3) -> list[dict]:
    """Get videos from a playlist. Costs 1 quota unit per page."""
    global quota_used
    videos = []
    page_token = None

    for _ in range(max_pages):
        quota_used += 1
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data = api_call("playlistItems", params)
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.warning(f"Playlist fetch failed: {e}")
            break

        for item in data.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "video_id": snippet["resourceId"]["videoId"],
                "title": snippet["title"],
                "channel": snippet.get("videoOwnerChannelTitle", ""),
                "published": snippet.get("publishedAt", ""),
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def search_videos(expert_name: str, max_results: int = 15) -> list[dict]:
    """Search for videos featuring an expert. Costs 100 quota units."""
    global quota_used
    quota_used += 100

    try:
        data = api_call("search", {
            "part": "snippet",
            "q": f'"{expert_name}" sales',
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
            "videoDuration": "medium",  # 4-20 minutes
        })
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.warning(f"Video search failed for {expert_name}: {e}")
        return []

    videos = []
    for item in data.get("items", []):
        snippet = item["snippet"]
        videos.append({
            "video_id": item["id"]["videoId"],
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "published": snippet.get("publishedAt", ""),
        })

    return videos


def is_sales_relevant(title: str) -> bool:
    """Check if a video title indicates sales-relevant content."""
    return bool(SALES_PATTERN.search(title))


def deduplicate_videos(videos: list[dict]) -> list[dict]:
    """Remove duplicate video IDs, keeping first occurrence."""
    seen = set()
    unique = []
    for v in videos:
        if v["video_id"] not in seen:
            seen.add(v["video_id"])
            unique.append(v)
    return unique


def curate_expert(expert_name: str) -> list[dict]:
    """Find relevant videos for a single expert.

    Strategy:
    1. Search for their YouTube channel → get uploads
    2. Search for videos mentioning them (guest appearances)
    3. Filter for sales relevance
    4. Deduplicate and cap at MAX_VIDEOS_PER_EXPERT
    """
    logger.info(f"Curating: {expert_name}")
    all_videos = []

    # 1. Try to find their channel and get uploads
    channel = search_channel(expert_name)
    if channel:
        uploads_id = get_uploads_playlist(channel["channel_id"])
        if uploads_id:
            upload_videos = get_playlist_videos(uploads_id, max_pages=3)
            logger.info(f"  Found {len(upload_videos)} uploads")
            # For own-channel uploads, be more lenient with filtering
            # (most content from a sales expert's channel is relevant)
            for v in upload_videos:
                v["source"] = "own_channel"
            all_videos.extend(upload_videos)

    # 2. Search for guest appearances / mentions
    search_results = search_videos(expert_name)
    logger.info(f"  Found {len(search_results)} search results")
    for v in search_results:
        v["source"] = "search"
    all_videos.extend(search_results)

    # 3. Deduplicate
    all_videos = deduplicate_videos(all_videos)

    # 4. Score and filter
    scored = []
    for v in all_videos:
        title = v["title"]
        # Skip private/deleted videos
        if title in ("Private video", "Deleted video"):
            continue

        # Own-channel videos get a base relevance score
        if v.get("source") == "own_channel":
            score = 5
        else:
            score = 0

        # Boost if title contains sales keywords
        matches = SALES_PATTERN.findall(title)
        score += len(set(matches)) * 3

        # Boost if expert name appears in title (guest appearance signal)
        if expert_name.lower().split()[-1] in title.lower():
            score += 2

        v["relevance_score"] = score
        scored.append(v)

    # Sort by relevance score descending
    scored.sort(key=lambda v: v["relevance_score"], reverse=True)

    # For own-channel experts: keep top videos even without keyword matches
    # For search-only experts: require at least some relevance
    if channel:
        # Expert has a channel — keep top uploads + relevant search results
        result = scored[:MAX_VIDEOS_PER_EXPERT]
    else:
        # No channel found — only keep videos with some relevance signal
        result = [v for v in scored if v["relevance_score"] >= 2][:MAX_VIDEOS_PER_EXPERT]

    logger.info(f"  Selected {len(result)} videos")
    return result


def load_experts() -> list[str]:
    """Load active, non-company expert names from influencers.json."""
    with open(INFLUENCERS_FILE) as f:
        data = json.load(f)

    experts = [
        inf["name"]
        for inf in data["influencers"]
        if inf.get("status") == "active"
    ]
    logger.info(f"Loaded {len(experts)} active experts")
    return experts


def load_existing_video_ids() -> set[str]:
    """Load video IDs already in collect_youtube.py's TARGET_VIDEOS."""
    collect_path = PROJECT_ROOT / "tools" / "collect_youtube.py"
    existing = set()
    with open(collect_path) as f:
        content = f.read()
    # Match video IDs in tuple format: ("VIDEO_ID", ...
    for match in re.finditer(r'\(\s*"([A-Za-z0-9_-]{11})"', content):
        existing.add(match.group(1))
    logger.info(f"Found {len(existing)} existing video IDs in TARGET_VIDEOS")
    return existing


def main():
    global quota_used

    if not YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY not set. Run via: ./run.sh curate_youtube")
        return

    experts = load_experts()
    existing_ids = load_existing_video_ids()

    results = {}
    experts_processed = 0

    try:
        for expert_name in experts:
            videos = curate_expert(expert_name)

            # Filter out videos already in TARGET_VIDEOS
            new_videos = [v for v in videos if v["video_id"] not in existing_ids]

            results[expert_name] = new_videos
            experts_processed += 1

            logger.info(
                f"  {len(new_videos)} new videos "
                f"({len(videos) - len(new_videos)} already existed) "
                f"[Quota: ~{quota_used}/10000]"
            )

    except QuotaExceededError:
        logger.warning(f"Quota exceeded after {experts_processed}/{len(experts)} experts")
        logger.warning("Saving partial results...")

    # Save full results
    output = {
        "curated_date": __import__("datetime").datetime.now().isoformat(),
        "experts_processed": experts_processed,
        "quota_used_estimate": quota_used,
        "experts": {},
    }

    total_new = 0
    for expert_name, videos in results.items():
        output["experts"][expert_name] = [
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "channel": v["channel"],
                "source": v.get("source", "unknown"),
                "relevance_score": v.get("relevance_score", 0),
            }
            for v in videos
        ]
        total_new += len(videos)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"Saved results to {OUTPUT_FILE}")

    # Print summary
    print("\n" + "=" * 60)
    print("CURATION SUMMARY")
    print("=" * 60)
    print(f"Experts processed: {experts_processed}/{len(experts)}")
    print(f"New videos found:  {total_new}")
    print(f"API quota used:    ~{quota_used}/10,000")
    print()

    # Print per-expert counts
    for expert_name in experts:
        videos = results.get(expert_name, [])
        count = len(videos)
        marker = " ✓" if count >= MIN_VIDEOS_PER_EXPERT else " ⚠ LOW" if count > 0 else " ✗ NONE"
        print(f"  {expert_name:30s} {count:3d} videos{marker}")

    # Print TARGET_VIDEOS-formatted tuples
    print("\n" + "=" * 60)
    print("TARGET_VIDEOS TUPLES (paste into collect_youtube.py)")
    print("=" * 60)
    for expert_name in experts:
        videos = results.get(expert_name, [])
        if not videos:
            continue
        print(f"    # {expert_name}")
        for v in videos:
            title_comment = v["title"][:60].replace('"', "'")
            channel = v["channel"].replace('"', "'")
            print(f'    ("{v["video_id"]}", "{expert_name}", "{channel}"),  # {title_comment}')

    print(f"\nTotal new entries: {total_new}")


if __name__ == "__main__":
    main()
