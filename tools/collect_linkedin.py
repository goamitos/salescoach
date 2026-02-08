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
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Sales Influencers (48 individual experts)
INFLUENCERS = [
    {
        "name": "Ian Koniak",
        "linkedin": "iankoniak",
        "focus": "enterprise sales, discovery",
    },
    {
        "name": "Nate Nasralla",
        "linkedin": "natenasralla",
        "focus": "discovery questions, qualification",
    },
    {
        "name": "Morgan J Ingram",
        "linkedin": "morganingram",
        "focus": "SDR, outbound, sequences",
    },
    {
        "name": "Armand Farrokh",
        "linkedin": "armandfarrokh",
        "focus": "discovery, sales methodology",
    },
    {
        "name": "Nick Cegelski",
        "linkedin": "nickcegelski",
        "focus": "cold calling, prospecting",
    },
    {
        "name": "Will Aitken",
        "linkedin": "willaitken",
        "focus": "sales leadership, coaching",
    },
    {"name": "Devin Reed", "linkedin": "devinreed", "focus": "content, copywriting"},
    {
        "name": "Florin Tatulea",
        "linkedin": "florin-tatulea",
        "focus": "LinkedIn selling, social selling",
    },
    {
        "name": "Kyle Coleman",
        "linkedin": "kylecoleman",
        "focus": "messaging, copy, GTM",
    },
    {
        "name": "Daniel Disney",
        "linkedin": "danieldisney",
        "focus": "LinkedIn selling, prospecting",
    },
    {
        "name": "Samantha McKenna",
        "linkedin": "samsalesli",
        "focus": "enterprise sales, LinkedIn",
    },
    {"name": "Gal Aga", "linkedin": "galaga", "focus": "sales alignment, methodology"},
    # --- Monday CRM Top 25 (18 new) ---
    {"name": "Anthony Iannarino", "linkedin": "iannarino", "focus": "B2B effectiveness, sales leadership"},
    {"name": "Giulio Segantini", "linkedin": "underdogsales", "focus": "cold calling mastery"},
    {"name": "Mark Hunter", "linkedin": "markhunter", "focus": "prospecting, pricing, leadership"},
    {"name": "Jill Konrath", "linkedin": "jillkonrath", "focus": "busy buyers, agile selling"},
    {"name": "Shari Levitin", "linkedin": "sharilevitin", "focus": "human-centered selling, storytelling"},
    {"name": "Jim Keenan", "linkedin": "jimkeenan", "focus": "Gap Selling, problem-centric discovery"},
    {"name": "Tiffani Bova", "linkedin": "tiffanibova", "focus": "GTM and growth strategy"},
    {"name": "Amy Volas", "linkedin": "amyvolas", "focus": "executive sales hiring, GTM"},
    {"name": "Ron Kimhi", "linkedin": "ron-kimhi", "focus": "CRM insights, GTM guidance"},
    {"name": "Chris Orlob", "linkedin": "chrisorlob", "focus": "deal mechanics, urgency creation"},
    {"name": "Becc Holland", "linkedin": "beccholland-flipthescript", "focus": "personalization-at-scale messaging"},
    {"name": "Jen Allen-Knuth", "linkedin": "demandjen1", "focus": "enterprise discovery, no-decision prevention"},
    {"name": "Alexandra Carter", "linkedin": "alexandrabcarter", "focus": "negotiation frameworks"},
    {"name": "Kwame Christian", "linkedin": "kwamechristian", "focus": "difficult conversation playbooks"},
    {"name": "Mo Bunnell", "linkedin": "mobunnell", "focus": "relationship-driven business development"},
    {"name": "Rosalyn Santa Elena", "linkedin": "rosalyn-santa-elena", "focus": "RevOps structure, metrics"},
    {"name": "Mark Kosoglow", "linkedin": "mkosoglow", "focus": "sales leadership, forecasting"},
    {"name": "Scott Leese", "linkedin": "scottleese", "focus": "pipeline building, team scaling"},
    # --- Proposify Best Sales Voices (14 new) ---
    {"name": "Sarah Brazier", "linkedin": "sjbrazier", "focus": "sales strategy, economic downturns"},
    {"name": "Jesse Gittler", "linkedin": "jesse-gittler-40019483", "focus": "SDR training and development"},
    {"name": "Chantel George", "linkedin": "chantelgeorge", "focus": "women of color advancement in sales"},
    {"name": "Bryan Tucker", "linkedin": "bryandtucker", "focus": "sales team scaling, employee advocacy"},
    {"name": "Colin Specter", "linkedin": "colinspecter", "focus": "AI-powered cold calling"},
    {"name": "Kevin Dorsey", "linkedin": "kddorsey3", "focus": "inside sales, revenue team training"},
    {"name": "Belal Batrawy", "linkedin": "belbatrawy", "focus": "cold outreach, messaging"},
    {"name": "Caroline Celis", "linkedin": "caroline-celis", "focus": "Latinx representation in sales/tech"},
    {"name": "Julie Hansen", "linkedin": "juliehansensalestraining", "focus": "virtual selling via video"},
    {"name": "Hannah Ajikawo", "linkedin": "hannah-ajikawo", "focus": "GTM strategy, EMEA market"},
    {"name": "Justin Michael", "linkedin": "michaeljustin", "focus": "cold calling, B2B demand acceleration"},
    {"name": "Erica Franklin", "linkedin": "erica-franklin", "focus": "DEI advocacy, enterprise account mgmt"},
    {"name": "Maria Bross", "linkedin": "mariabross", "focus": "SDR call reluctance, coaching"},
    {"name": "Niraj Kapur", "linkedin": "nkapur", "focus": "building trust with prospects"},
    # --- OG16 missing from original list ---
    {"name": "John Barrows", "linkedin": "johnbarrows", "focus": "enterprise selling, prospecting"},
    {"name": "Josh Braun", "linkedin": "josh-braun", "focus": "cold outreach, objection handling"},
    {"name": "Jeb Blount", "linkedin": "jebblount", "focus": "prospecting, sales leadership"},
    {"name": "Chris Voss", "linkedin": "christophervoss", "focus": "negotiation, tactical empathy"},
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
