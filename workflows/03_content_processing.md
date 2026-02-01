# Content Processing with Claude

## Overview
Use Claude API to analyze, categorize, and extract insights from collected content.

## Deal Stages (Categorization Targets)
1. Territory Planning
2. Account Research
3. Stakeholder Mapping
4. Outreach Strategy
5. Initial Contact
6. Discovery
7. Needs Analysis
8. Demo & Presentation
9. Business Case Development
10. Proof of Value
11. RFP/RFQ Response
12. Procurement & Negotiation
13. Closing
14. Onboarding & Expansion
15. General Sales Mindset

## Claude API Configuration
- Model: `claude-sonnet-4-20250514`
- Max tokens: 1500
- Temperature: 0.3 (for consistent categorization)

## Analysis Prompt Template
```
Analyze this sales content and extract structured insights.

CONTENT:
{content}

SOURCE: {source_type} by {influencer}

Respond in JSON format:
{
  "primary_stage": "One of the 15 deal stages",
  "secondary_stages": ["Up to 2 additional relevant stages"],
  "key_insight": "One sentence summary of the main wisdom",
  "tactical_steps": ["2-4 actionable steps from the content"],
  "keywords": ["5-8 searchable keywords"],
  "situation_examples": ["1-2 specific scenarios where this applies"],
  "best_quote": "Most memorable/quotable line from content",
  "relevance_score": 1-10
}

Only include content with clear, actionable sales wisdom.
Score 7+ for highly tactical content, 5-6 for general advice, below 5 for tangential content.
```

## Quality Thresholds
- Relevance score >= 7: Include in final export
- Relevance score 5-6: Review manually
- Relevance score < 5: Exclude

## Rate Limiting
- 2 seconds between Claude API calls
- Process in batches of 10
- Monitor token usage

## Output Format
Save to `.tmp/processed_content.json`:
```json
{
  "processed": [
    {
      "source_id": "unique_id",
      "influencer": "John Barrows",
      "source_type": "linkedin",
      "source_url": "https://...",
      "date_collected": "2024-01-15",
      "primary_stage": "Discovery",
      "secondary_stages": ["Needs Analysis"],
      "key_insight": "...",
      "tactical_steps": ["..."],
      "keywords": ["..."],
      "situation_examples": ["..."],
      "best_quote": "...",
      "relevance_score": 8
    }
  ]
}
```

## Tool
```bash
python tools/process_content.py
```

## Cost Awareness
- Estimate tokens before processing
- Log API costs per batch
- Ask before processing large batches (100+ items)

## Next Step
After processing, proceed to `04_airtable_export.md`
