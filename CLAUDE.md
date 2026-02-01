# Sales Coach

Automated pipeline that scrapes sales wisdom from LinkedIn/YouTube, categorizes by deal stage, stores in Airtable, and provides AI-powered Q&A.

## Tech Stack
- Python 3.10+
- Claude API (content analysis, categorization)
- Airtable API (storage, AI fields for Q&A)
- BeautifulSoup (HTML parsing)
- youtube-transcript-api (transcript extraction)

## Project Structure
```
salescoach/
├── tools/              # Pipeline scripts (scraping, processing, API calls)
│   └── ask_coach.py    # CLI-based Q&A tool
├── streamlit_app.py    # Web UI for Q&A (deployable to Streamlit Cloud)
├── workflows/          # Markdown SOPs for each pipeline stage
├── docs/               # Setup guides and documentation
├── .tmp/               # Intermediate files (disposable)
├── .env.tpl            # 1Password secret references (safe to commit)
├── run.sh              # Local runner with 1Password secret injection
├── outputs/            # Final CSVs for Airtable import
└── .github/workflows/  # GitHub Actions for weekly automation
```

## Commands

### Local Development (with 1Password)
- `./run.sh collect_linkedin` - Step 1: Google X-ray LinkedIn posts
- `./run.sh collect_youtube` - Step 2: YouTube transcript extraction
- `./run.sh process_content` - Step 3: Claude categorization
- `./run.sh push_airtable` - Step 4: Push to Airtable

### Setup
- `pip install -r requirements.txt` - Install dependencies
- `brew install 1password-cli` - Install 1Password CLI
- `op signin` - Sign in to 1Password

### GitHub Actions
- Weekly automation runs every Monday 9am UTC
- Manual trigger: GitHub Actions → "Weekly LinkedIn Collection" → Run workflow

## WAT Architecture

You operate as the Agent layer - reading workflows, executing tools, handling failures.

### Directories
- `workflows/` - Read BEFORE executing tasks
- `tools/` - Run scripts; don't rewrite unless fixing bugs
- `.tmp/` - Disposable intermediate files
- Secrets stored in 1Password (vault: SalesCoach), injected at runtime via `run.sh`

### Operating Principles
1. Check `tools/` before writing new scripts
2. On errors: read trace, fix script, document in workflow
3. Keep workflows current with learnings
4. Ask before making paid API calls (Claude API costs money)

## Key Patterns

### Content Processing
- All scraping outputs go to `.tmp/` as JSON
- Claude API calls use `claude-sonnet-4-20250514` model
- Rate limit: 2s between Claude API calls, 3s between scrape batches
- Relevance threshold: score >= 7 to include content

### Deal Stages (for categorization)
Territory Planning, Account Research, Stakeholder Mapping, Outreach Strategy, Initial Contact, Discovery, Needs Analysis, Demo & Presentation, Business Case Development, Proof of Value, RFP/RFQ Response, Procurement & Negotiation, Closing, Onboarding & Expansion, General Sales Mindset

### Data Schema (Airtable)
Influencer | Source Type | Source URL | Date Collected | Primary Stage | Secondary Stages | Key Insight | Tactical Steps | Keywords | Situation Examples | Best Quote | Relevance Score

## Important Constraints
- Never commit credentials (secrets are in 1Password, injected at runtime)
- LinkedIn scraping via Google X-ray only (not direct scraping)
- Attribute all content to original creators
- Store intermediate files in `.tmp/`, final outputs in `outputs/`

## Security Setup
- **Local**: 1Password CLI injects secrets via `run.sh` (never written to disk)
- **GitHub Actions**: Secrets stored in GitHub Secrets (encrypted)
- **Vault**: 1Password vault "SalesCoach" with item "SalesCoach"
- **Keys**: ANTHROPIC_API_KEY, AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, SERPER_API_KEY

## AI-Powered Q&A

### Overview
Two options for "Ask the Coach" natural language Q&A:
1. **CLI Tool**: `./run.sh ask_coach` - quick terminal-based Q&A
2. **Streamlit Web App**: Beautiful web UI, deployable to Streamlit Cloud

### CLI Tool
Location: `tools/ask_coach.py`

```bash
./run.sh ask_coach
# Describe your situation: ___
# Returns synthesized coaching advice with sources
```

### Streamlit Web App
Location: `streamlit_app.py`

**Run locally:**
```bash
streamlit run streamlit_app.py
```

**Deploy to Streamlit Cloud:**
1. Push repo to GitHub
2. Go to share.streamlit.io → New app
3. Select your repo and `streamlit_app.py`
4. Add secrets in App Settings → Secrets:
   - `ANTHROPIC_API_KEY`
   - `AIRTABLE_API_KEY`
   - `AIRTABLE_BASE_ID`
   - `AIRTABLE_TABLE_NAME`

### Demo Questions
- "I'm in discovery with a CFO who seems distracted"
- "The procurement team is pushing back on pricing"
- "How do I create urgency without being pushy?"
- "The prospect went silent after my demo"

### Airtable Interface (Browse Mode)
Use Airtable's Interface Designer for browsing:
- Filter by deal stage, influencer, keywords
- Click cards to see full insights
- Works on free Airtable plan
