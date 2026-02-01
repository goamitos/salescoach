# LinkedIn Content Collection

## Overview
Collect sales wisdom from LinkedIn posts using Google X-ray search (not direct LinkedIn scraping).

## Google X-ray Search Patterns

### Base Pattern
```
site:linkedin.com/posts [influencer name] [topic]
```

### Example Queries
```
site:linkedin.com/posts "sales discovery" tips
site:linkedin.com/posts "cold calling" framework
site:linkedin.com/posts "enterprise sales" strategy
site:linkedin.com/posts "john barrows" sales
site:linkedin.com/posts "josh braun" prospecting
```

### Target Influencers
- John Barrows
- Josh Braun
- Morgan Ingram
- Jeb Blount
- Keenan (Gap Selling)
- Chris Voss
- Gong.io team
- Add more as discovered

## Rate Limiting Strategy
- 3 seconds between Google search requests
- 2 seconds between page fetches
- Max 20 requests per session
- Rotate user agents

## Output Format
Save to `.tmp/linkedin_raw.json`:
```json
{
  "posts": [
    {
      "influencer": "John Barrows",
      "url": "https://linkedin.com/posts/...",
      "content": "Full post text...",
      "date_collected": "2024-01-15",
      "source_type": "linkedin"
    }
  ]
}
```

## Tool
```bash
python tools/collect_linkedin.py
```

## Error Handling
- If rate limited: wait 60s, retry with reduced batch
- If blocked: switch user agent, reduce frequency
- Log all failures to `.tmp/linkedin_errors.log`

## Next Step
After collection, proceed to `03_content_processing.md`
