"""
Shared configuration for Sales Coach tools.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Sales Wisdom")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"
DATA_DIR = PROJECT_ROOT / "data"
INFLUENCERS_PATH = DATA_DIR / "influencers.json"
PERSONAS_PATH = DATA_DIR / "personas.json"

# Ensure directories exist
TMP_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# Rate limiting (seconds)
RATE_LIMIT_CLAUDE = 2.0
RATE_LIMIT_SCRAPE = 3.0
RATE_LIMIT_YOUTUBE = 2.0

# Processing thresholds
RELEVANCE_THRESHOLD = 7

# Claude API settings
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS = 1500
CLAUDE_TEMPERATURE = 0.3

# Persona generation settings (Sonnet for voice analysis nuance)
PERSONA_CLAUDE_MODEL = "claude-sonnet-4-20250514"
PERSONA_MAX_TOKENS = 4000
PERSONA_TEMPERATURE = 0.4
PERSONA_POLL_INTERVAL = 30

# Persona confidence thresholds
PERSONA_HIGH_INSIGHTS = 20
PERSONA_HIGH_CHARS = 30_000
PERSONA_MEDIUM_INSIGHTS = 10
PERSONA_MEDIUM_CHARS = 10_000

# Deal stages for categorization
DEAL_STAGES = [
    "Territory Planning",
    "Account Research",
    "Stakeholder Mapping",
    "Outreach Strategy",
    "Initial Contact",
    "Discovery",
    "Needs Analysis",
    "Demo & Presentation",
    "Business Case Development",
    "Proof of Value",
    "RFP/RFQ Response",
    "Procurement & Negotiation",
    "Closing",
    "Onboarding & Expansion",
    "General Sales Mindset",
]

# User agents for scraping
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


def get_random_user_agent():
    """Return a random user agent string."""
    import random

    return random.choice(USER_AGENTS)
