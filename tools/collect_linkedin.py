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
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import (
    TMP_DIR,
    RATE_LIMIT_SCRAPE,
    SERPER_API_KEY,
    get_random_user_agent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Top 12 LinkedIn Sales Voices (from plan.md)
INFLUENCERS = [
    {"name": "Ian Koniak", "linkedin": "iankoniak", "focus": "enterprise sales, discovery"},
    {"name": "Nate Nasralla", "linkedin": "natenasralla", "focus": "discovery questions, qualification"},
    {"name": "Morgan J Ingram", "linkedin": "morganingram", "focus": "SDR, outbound, sequences"},
    {"name": "Armand Farrokh", "linkedin": "armandfarrokh", "focus": "discovery, sales methodology"},
    {"name": "Nick Cegelski", "linkedin": "nickcegelski", "focus": "cold calling, prospecting"},
    {"name": "Will Aitken", "linkedin": "willaitken", "focus": "sales leadership, coaching"},
    {"name": "Devin Reed", "linkedin": "devinreed", "focus": "content, copywriting"},
    {"name": "Florin Tatulea", "linkedin": "florin-tatulea", "focus": "LinkedIn selling, social selling"},
    {"name": "Kyle Coleman", "linkedin": "kylecoleman", "focus": "messaging, copy, GTM"},
    {"name": "Daniel Disney", "linkedin": "danieldisney", "focus": "LinkedIn selling, prospecting"},
    {"name": "Samantha McKenna", "linkedin": "samsalesli", "focus": "enterprise sales, LinkedIn"},
    {"name": "Gal Aga", "linkedin": "galaga", "focus": "sales alignment, methodology"},
]

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


def search_serper(query: str, num_results: int = 10) -> list[dict]:
    """
    Perform Google search via Serper.dev API.
    Returns list of search results with URLs.
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY not set in .env")
        return []

    url = "https://google.serper.dev/search"

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "q": query,
        "num": num_results,
        "tbs": "qdr:y"  # Last year
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("organic", []):
            link = item.get("link", "")
            if "linkedin.com/posts/" in link or "linkedin.com/pulse/" in link:
                results.append({
                    "url": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })

        return results

    except Exception as e:
        logger.error(f"Serper API error: {e}")
        return []


def build_influencer_queries() -> list[dict]:
    """Generate search queries for each influencer."""
    queries = []

    for inf in INFLUENCERS:
        # Primary query: influencer's posts
        queries.append({
            "query": f'site:linkedin.com/posts/ "{inf["linkedin"]}"',
            "influencer": inf["name"],
            "type": "profile"
        })

        # Secondary: influencer name + sales topic
        queries.append({
            "query": f'site:linkedin.com/posts/ "{inf["name"]}" sales',
            "influencer": inf["name"],
            "type": "name_topic"
        })

    return queries


def fetch_post_preview(url: str) -> dict | None:
    """
    Fetch LinkedIn post preview content.
    Gets meta description and og:description which contain post preview.
    """
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

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


def collect_posts():
    """Main collection function."""
    logger.info("=" * 60)
    logger.info("LINKEDIN COLLECTION VIA SERPER.DEV")
    logger.info("=" * 60)

    if not SERPER_API_KEY:
        logger.error("Missing SERPER_API_KEY in .env file")
        logger.error("Get free key at: https://serper.dev")
        return None

    queries = build_influencer_queries()
    logger.info(f"Built {len(queries)} search queries for {len(INFLUENCERS)} influencers")

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
