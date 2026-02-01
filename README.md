# Sales Coach

AI-powered sales coaching that learns from top sales influencers. Get personalized advice for any deal stage, backed by wisdom from 13 industry experts.

**Try it now:** [ask-the-coach.streamlit.app](https://ask-the-coach.streamlit.app/)

## What It Does

Sales Coach automatically:
1. **Collects** sales content from LinkedIn posts and YouTube videos
2. **Categorizes** insights by deal stage using Claude AI
3. **Stores** everything in Airtable for easy browsing
4. **Answers** your sales questions with synthesized coaching advice

## Features

- **Ask the Coach** - Natural language Q&A powered by Claude
- **Stage-Based Insights** - Content organized by 15 deal stages
- **Source Attribution** - Every insight links back to the original creator
- **Web & CLI** - Beautiful Streamlit app or quick terminal access
- **Weekly Updates** - Automated pipeline keeps content fresh

## Quick Start

### Prerequisites

- Python 3.10+
- [1Password CLI](https://developer.1password.com/docs/cli/) (for local development)
- API keys: Anthropic, Airtable, Serper

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/salescoach.git
cd salescoach

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up 1Password (optional, for local secrets)
brew install 1password-cli
op signin
```

### Configuration

Create a 1Password vault named "SalesCoach" with these secrets:
- `ANTHROPIC_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_TABLE_NAME`
- `SERPER_API_KEY`

Or set environment variables directly for testing.

## Usage

### Ask the Coach (CLI)

```bash
./run.sh ask_coach
# Describe your situation: The prospect went silent after my demo
# → Returns synthesized coaching advice with sources
```

### Ask the Coach (Web App)

```bash
./run.sh streamlit
# Opens at http://localhost:8501
```

### Run the Pipeline

```bash
# Step 1: Collect LinkedIn posts via Google X-ray
./run.sh collect_linkedin

# Step 2: Extract YouTube transcripts
./run.sh collect_youtube

# Step 3: Categorize with Claude AI
./run.sh process_content

# Step 4: Push to Airtable
./run.sh push_airtable
```

## Deal Stages

Content is categorized into 15 stages covering the full sales cycle:

| Phase | Stages |
|-------|--------|
| **Planning & Research** | Territory Planning, Account Research, Stakeholder Mapping |
| **Outreach & Contact** | Outreach Strategy, Initial Contact |
| **Discovery & Analysis** | Discovery, Needs Analysis |
| **Present & Prove Value** | Demo & Presentation, Business Case Development, Proof of Value |
| **Close & Grow** | RFP/RFQ Response, Procurement & Negotiation, Closing, Onboarding & Expansion |
| **Always Relevant** | General Sales Mindset |

## Influencers

Insights are sourced from 13 top sales voices:

- **30MPC** (Armand Farrokh & Nick Cegelski)
- **Samantha McKenna** (#samsales)
- **Ian Koniak**
- **Morgan J Ingram**
- **Kyle Coleman**
- **And 8 more...**

See [docs/influencers.md](docs/influencers.md) for full profiles and links.

## Tech Stack

- **AI**: Claude API (Anthropic) for content analysis and Q&A
- **Storage**: Airtable for structured data and browsing
- **Web**: Streamlit for the chat interface
- **Scraping**: BeautifulSoup + youtube-transcript-api
- **Automation**: GitHub Actions for weekly collection

## Deploy to Streamlit Cloud

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select your repo and `streamlit_app.py`
4. Add secrets in App Settings → Secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-..."
   AIRTABLE_API_KEY = "pat..."
   AIRTABLE_BASE_ID = "app..."
   AIRTABLE_TABLE_NAME = "Sales Wisdom"
   ```

## Project Structure

```
salescoach/
├── tools/                  # Pipeline scripts
│   ├── ask_coach.py        # CLI Q&A tool
│   ├── collect_linkedin.py # LinkedIn scraper
│   ├── collect_youtube.py  # YouTube transcript extractor
│   ├── process_content.py  # Claude categorization
│   └── push_airtable.py    # Airtable uploader
├── streamlit_app.py        # Web UI
├── assets/avatars/         # Influencer profile pictures
├── docs/                   # Documentation
├── workflows/              # SOPs for each pipeline stage
├── .github/workflows/      # GitHub Actions automation
└── run.sh                  # Local runner with 1Password
```

## License

MIT

## Acknowledgments

All insights are attributed to their original creators. This tool aggregates and categorizes publicly available content for educational purposes.
