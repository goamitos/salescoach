# YouTube Content Collection

## Overview
Extract transcripts from sales-focused YouTube videos and channels.

## Target Channels
- Sales Gravy (Jeb Blount)
- JBarrows Sales Training
- Josh Braun
- Chris Voss (MasterClass clips)
- Gong.io
- Sandler Training
- RAIN Group
- Add more as discovered

## Discovery Methods

### Search Queries
```
sales discovery call tips
cold calling framework 2024
enterprise sales strategy
B2B sales negotiation
handling sales objections
```

### Playlist Mining
Look for playlists titled:
- "Sales Training"
- "Cold Calling Tips"
- "Discovery Call Mastery"
- "Negotiation Tactics"

## Transcript Extraction

### Using youtube-transcript-api
```python
from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript(video_id)
full_text = ' '.join([entry['text'] for entry in transcript])
```

### Chunking Strategy
- Split transcripts into ~500 word chunks
- Preserve sentence boundaries
- Overlap 50 words between chunks for context

## Rate Limiting
- 2 seconds between transcript requests
- Max 50 videos per session
- Respect YouTube's rate limits

## Output Format
Save to `.tmp/youtube_raw.json`:
```json
{
  "videos": [
    {
      "influencer": "John Barrows",
      "channel": "JBarrows Sales Training",
      "video_id": "abc123",
      "title": "Discovery Call Framework",
      "url": "https://youtube.com/watch?v=abc123",
      "transcript_chunks": [
        {
          "chunk_index": 0,
          "content": "First 500 words...",
          "start_time": 0
        }
      ],
      "date_collected": "2024-01-15",
      "source_type": "youtube"
    }
  ]
}
```

## Tool
```bash
python tools/collect_youtube.py
```

## Error Handling
- No transcript available: log and skip
- Rate limited: exponential backoff
- Log failures to `.tmp/youtube_errors.log`

## Next Step
After collection, proceed to `03_content_processing.md`
