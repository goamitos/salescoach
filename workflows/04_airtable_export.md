# Airtable Export

## Overview
Export processed content to CSV format for Airtable import, then configure AI fields for Q&A.

## CSV Schema
| Column | Type | Description |
|--------|------|-------------|
| Influencer | Text | Content creator name |
| Source Type | Single Select | linkedin, youtube |
| Source URL | URL | Original content link |
| Date Collected | Date | When content was scraped |
| Primary Stage | Single Select | Main deal stage |
| Secondary Stages | Multi-select | Additional deal stages |
| Key Insight | Long Text | One sentence summary |
| Tactical Steps | Long Text | Actionable steps (newline separated) |
| Keywords | Multi-select | Searchable tags |
| Situation Examples | Long Text | When to apply this |
| Best Quote | Long Text | Memorable line |
| Relevance Score | Number | 1-10 quality score |

## Export Process

### 1. Generate CSV
```bash
python tools/export_airtable.py
```

Output: `outputs/sales_wisdom_YYYYMMDD.csv`

### 2. Import to Airtable
1. Open Airtable base
2. Create new table or use existing
3. Import CSV (File > Import > CSV)
4. Map columns to field types
5. Set Single Select options for stages

## AI Field Setup (Airtable AI Extension)

### Recommended AI Fields

**1. Stage Coach**
- Type: AI Generated
- Prompt: "Based on the Key Insight and Tactical Steps, provide a brief coaching tip for a rep currently in the {Primary Stage} stage."

**2. Quick Summary**
- Type: AI Generated
- Prompt: "In 15 words or less, summarize the actionable advice from this record."

**3. Related Question**
- Type: AI Generated
- Prompt: "Generate one discovery question a sales rep could ask their prospect based on this insight."

### Q&A Interface Setup
1. Create a new Interface in Airtable
2. Add a form for asking questions
3. Use AI blocks to search and answer based on table content
4. Filter by Primary Stage for contextual answers

## Automation Ideas

### New Content Alert
- Trigger: New record created
- Action: Send Slack notification with Key Insight

### Weekly Digest
- Trigger: Every Monday 8am
- Action: Email top 5 insights by Relevance Score

## Tool
```bash
python tools/export_airtable.py
```

## Verification
After import:
- [ ] All rows imported correctly
- [ ] Single selects have correct options
- [ ] URLs are clickable
- [ ] AI fields generating properly

## Maintenance
- Run full pipeline weekly
- Deduplicate by Source URL before import
- Archive records older than 6 months to separate table
