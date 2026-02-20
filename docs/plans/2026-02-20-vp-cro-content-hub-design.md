# VP/CRO Content Hub — Design

## Problem

The Sales Coach DB has 1,893 insights categorized by deal stage and methodology, but nothing distinguishes content relevant to VP Sales/CROs from content for AEs or SDRs. The user wants a filtered, searchable collection of leadership-relevant content with AI-powered insights.

## Approach

Claude Haiku Batch API re-classifies all existing insights by target audience. Store results in SQLite. Expose via CLI and Streamlit.

## Schema Change

Three new columns on the `insights` table:

| Column | Type | Description |
|--------|------|-------------|
| `target_audience` | TEXT | JSON array: `["vp_sales", "cro"]`. Values: `vp_sales`, `cro`, `director`, `manager`, `ae`, `sdr`, `general` |
| `audience_confidence` | REAL | 0.0–1.0 |
| `audience_reasoning` | TEXT | One-sentence explanation |

A record is "VP/CRO relevant" if `target_audience` contains `vp_sales` or `cro` with confidence >= 0.7.

## Classification Pipeline

**Script:** `tools/classify_audience.py`

1. Load all insights from SQLite
2. Skip already-tagged records (idempotent)
3. Submit to Claude Haiku Batch API with audience classification prompt
4. Parse responses, write to SQLite

**Prompt core:**

> Classify who this sales insight is most useful for. The question is: "Who would act on this advice?"
> - `vp_sales` / `cro`: Managing teams, building pipeline strategy, forecasting, coaching reps, board reporting, org design
> - `director` / `manager`: First-line leadership, deal coaching, team enablement
> - `ae`: Running deals, discovery calls, demos, negotiations, closing
> - `sdr`: Prospecting, cold outreach, booking meetings
> - `general`: Applicable across all roles

**Model:** claude-haiku-4-5-20251001 via Batch API (50% cost savings)
**Estimated cost:** ~$0.60 for 1,893 records

**Forward integration:** Update `process_content.py` prompt to include audience classification for new content.

## CLI — `coach` Command

Install via `pip install -e .` using a `pyproject.toml` entry point (or lightweight wrapper script).

```
coach ask "question"                    # General Q&A (all insights)
coach leaders "query"                   # Search VP/CRO subset (FTS5)
coach leaders --ask "question"          # AI-synthesized answer from VP/CRO content
coach search --stage Discovery "query"  # Filtered search across all content
```

Wraps 1Password secret injection internally.

## Streamlit — Leadership Hub Tab

New tab in the existing multipage app.

**Top — Aggregate stats:**
- Total VP/CRO insights vs total DB
- Stage breakdown (bar chart)
- Top influencers for leadership content
- Top keyword clusters

**Middle — Browse & filter:**
- Filters: stage, influencer, confidence threshold
- Searchable table with expand-to-detail

**Bottom — AI Q&A:**
- Chat interface scoped to VP/CRO subset
- Claude-synthesized answers with source attribution

## Out of Scope

- No Airtable schema changes
- No new scraping or content collection
- No vector/embedding search
- No changes to existing `ask_coach` behavior
