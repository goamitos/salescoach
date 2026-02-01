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
├── tools/              # Deterministic scripts (scraping, API calls)
├── workflows/          # Markdown SOPs for each pipeline stage
├── .tmp/               # Intermediate files (disposable)
├── .env                # API keys (ANTHROPIC_API_KEY, AIRTABLE_API_KEY)
└── outputs/            # Final CSVs for Airtable import
```

## Commands
- `pip install -r requirements.txt` - Install dependencies
- `python tools/collect_linkedin.py` - Step 1: Google X-ray LinkedIn posts
- `python tools/collect_youtube.py` - Step 2: YouTube transcript extraction
- `python tools/process_content.py` - Step 3: Claude categorization
- `python tools/export_airtable.py` - Step 4: Generate Airtable CSV

## WAT Architecture

You operate as the Agent layer - reading workflows, executing tools, handling failures.

### Directories
- `workflows/` - Read BEFORE executing tasks
- `tools/` - Run scripts; don't rewrite unless fixing bugs
- `.tmp/` - Disposable intermediate files
- `.env` - Secrets (never commit, never expose)

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
- Never commit `.env` or credentials
- LinkedIn scraping via Google X-ray only (not direct scraping)
- Attribute all content to original creators
- Store intermediate files in `.tmp/`, final outputs in `outputs/`
