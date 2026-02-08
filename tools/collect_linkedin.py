#!/usr/bin/env python3
"""
LinkedIn Content Collection via Google X-ray Search (Serper.dev)

Collects sales wisdom from LinkedIn posts using Google search
(site:linkedin.com/posts) to avoid direct LinkedIn scraping.

Usage:
    python tools/collect_linkedin.py

Output:
    .tmp/linkedin_raw.json
"""
import json
import time
from typing import Any, Optional
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    TMP_DIR,
    RATE_LIMIT_SCRAPE,
    SERPER_API_KEY,
    get_random_user_agent,
    load_influencer_registry,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Sales Influencers — loaded from data/influencers.json (single source of truth)
def _build_influencer_list():
    """Build influencer list from the registry."""
    result = []
    for expert in load_influencer_registry():
        if expert.get("status") != "active":
            continue
        handle = expert.get("platforms", {}).get("linkedin", {}).get("handle")
        if not handle:
            continue
        result.append({
            "name": expert["name"],
            "linkedin": handle,
            "focus": ", ".join(expert.get("metadata", {}).get("focus_areas", [])),
        })
    return result


INFLUENCERS = _build_influencer_list()

# Sales keywords for enhanced searches
SALES_KEYWORDS = [
    "discovery call",
    "cold calling",
    "prospecting",
    "objection handling",
    "enterprise sales",
    "qualification",
]

OUTPUT_FILE = TMP_DIR / "linkedin_raw.json"
ERROR_LOG = TMP_DIR / "linkedin_errors.log"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    reraise=True,
)
def _serper_request(url: str, headers: dict[str, str], payload: dict[str, any]) -> dict[str, any]:
    """Make HTTP request to Serper API with retry logic."""
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def search_serper(query: str, num_results: int = 10) -> list[dict]:
    """
    Perform Google search via Serper.dev API.
    Returns list of search results with URLs.
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY not set in .env")
        return []

    url = "https://google.serper.dev/search"

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    payload = {"q": query, "num": num_results, "tbs": "qdr:y"}  # Last year

    try:
        data = _serper_request(url, headers, payload)
        results = []

        for item in data.get("organic", []):
            link = item.get("link", "")
            if "linkedin.com/posts/" in link or "linkedin.com/pulse/" in link:
                results.append(
                    {
                        "url": link,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                    }
                )

        return results

    except Exception as e:
        logger.error(f"Serper API error: {e}")
        return []


def build_influencer_queries() -> list[dict[str, str]]:
    """Generate search queries for each influencer."""
    queries = []

    for inf in INFLUENCERS:
        # Primary query: influencer's posts
        queries.append(
            {
                "query": f'site:linkedin.com/posts/ "{inf["linkedin"]}"',
                "influencer": inf["name"],
                "type": "profile",
            }
        )

        # Secondary: influencer name + sales topic
        queries.append(
            {
                "query": f'site:linkedin.com/posts/ "{inf["name"]}" sales',
                "influencer": inf["name"],
                "type": "name_topic",
            }
        )

    return queries


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    reraise=True,
)
def _fetch_url(url: str, headers: dict[str, str]) -> str:
    """Fetch URL content with retry logic."""
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def fetch_post_preview(url: str) -> Optional[dict]:
    """
    Fetch LinkedIn post preview content.
    Gets meta description and og:description which contain post preview.
    """
    try:
        headers = {"User-Agent": get_random_user_agent()}
        html_content = _fetch_url(url, headers)

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract content from meta tags (LinkedIn previews)
        content_parts = []

        # og:description usually has the post text
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            content_parts.append(og_desc["content"])

        # Regular description as backup
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"]
            if desc not in content_parts:
                content_parts.append(desc)

        # og:title for context
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else ""

        content = " ".join(content_parts)

        if len(content) < 50:
            logger.warning(f"Short content for {url}: {len(content)} chars")
            return None

        return {
            "url": url,
            "title": title,
            "content": content[:3000],
            "content_length": len(content),
        }

    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        with open(ERROR_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {url} - {e}\n")
        return None


def collect_posts() -> Optional[dict[str, Any]]:
    """Main collection function."""
    logger.info("=" * 60)
    logger.info("LINKEDIN COLLECTION VIA SERPER.DEV")
    logger.info("=" * 60)

    if not SERPER_API_KEY:
        logger.error("Missing SERPER_API_KEY in .env file")
        logger.error("Get free key at: https://serper.dev")
        return None

    queries = build_influencer_queries()
    logger.info(
        f"Built {len(queries)} search queries for {len(INFLUENCERS)} influencers"
    )

    all_posts = []
    seen_urls = set()
    search_count = 0

    for q in queries:
        logger.info(f"Searching: {q['influencer']} ({q['type']})")

        results = search_serper(q["query"], num_results=10)
        search_count += 1

        logger.info(f"  Found {len(results)} LinkedIn results")

        for result in results:
            url = result["url"]

            # Dedupe
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Fetch actual content
            logger.info(f"  Fetching: {url[:60]}...")
            post_data = fetch_post_preview(url)

            if post_data:
                post_data["influencer"] = q["influencer"]
                post_data["search_snippet"] = result.get("snippet", "")
                post_data["date_collected"] = datetime.now().isoformat()
                post_data["source_type"] = "linkedin"
                all_posts.append(post_data)
                logger.info(f"    ✓ Got {post_data['content_length']} chars")
            else:
                logger.info(f"    ✗ Could not fetch content")

            time.sleep(RATE_LIMIT_SCRAPE)

        time.sleep(1)  # Brief pause between searches

    # Save results
    output = {
        "posts": all_posts,
        "collection_date": datetime.now().isoformat(),
        "search_count": search_count,
        "influencer_count": len(INFLUENCERS),
        "unique_posts": len(all_posts),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"COLLECTION COMPLETE")
    logger.info(f"  Searches: {search_count}")
    logger.info(f"  Posts collected: {len(all_posts)}")
    logger.info(f"  Output: {OUTPUT_FILE}")
    logger.info("=" * 60)

    return output


if __name__ == "__main__":
    collect_posts()
