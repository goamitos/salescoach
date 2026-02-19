# Architecture Spec — Sales Coach

## Overview
Automated pipeline that scrapes sales wisdom from LinkedIn/YouTube, categorizes by deal stage, stores in Airtable, and provides AI-powered Q&A.

## Tech Stack
- Python 3.10+
- Claude API (content analysis, categorization)
- Airtable API (storage, AI fields for Q&A)
- Streamlit (web UI for Q&A chat)
- BeautifulSoup (HTML parsing)
- youtube-transcript-api (transcript extraction)
- 1Password CLI (secret injection)

## Pipeline Architecture
```
collect_linkedin → collect_youtube → process_content → push_airtable
     (Google X-ray)    (transcripts)     (Claude classify)   (Airtable API)
         ↓                  ↓                  ↓                  ↓
      .tmp/json          .tmp/json          .tmp/json         outputs/csv
```

## Directory Structure
- `tools/` — Pipeline scripts (one per stage)
- `components/` — Streamlit UI components
- `utils/` — Shared utilities
- `pages/` — Streamlit multi-page app pages
- `workflows/` — Markdown SOPs for each pipeline stage
- `data/` — SQLite DB and runtime data
- `.tmp/` — Disposable intermediate files
- `outputs/` — Final CSVs for Airtable import

## Design Decisions
- 1Password for secrets (no .env files with real values)
- Google X-ray for LinkedIn (avoids direct scraping ToS issues)
- Airtable as primary storage (low-friction, AI fields for Q&A)
- Streamlit for web UI (fast to build, easy to deploy)
