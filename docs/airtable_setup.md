# Airtable Setup Guide

This guide walks you through setting up the AI-powered Sales Coach, including the Airtable Interface for browsing and the standalone Q&A tools.

## Prerequisites

- Airtable account (free tier works)
- Anthropic API key for the "Ask Coach" tools
- Data already imported via `push_airtable.py`

---

## Step 1: Verify Table Schema

Your "Sales Wisdom" table should have these fields:

| Field Name | Type | Purpose |
|------------|------|---------|
| Source ID | Single line text | Unique identifier for deduplication |
| Influencer | Single line text | Content creator name |
| Source Type | Single select | "LinkedIn" or "Youtube" |
| Source URL | URL | Original content link |
| Date Collected | Date | When content was scraped |
| Primary Stage | Single select | Main deal stage category |
| Secondary Stages | Long text | Additional relevant stages |
| Key Insight | Long text | Main takeaway summary |
| Tactical Steps | Long text | Actionable bullet points |
| Keywords | Long text | Searchable terms |
| Situation Examples | Long text | When to apply this advice |
| Best Quote | Long text | Memorable line from content |
| Relevance Score | Number | 1-10 quality rating |

---

## Step 2: Create the Airtable Interface (Browse Mode)

### 2.1 Open Interface Designer
1. Click **Interfaces** in the top bar (or create one)
2. Click **+ Create interface** → Start from scratch
3. Name it: "Sales Coach"

### 2.2 Add Header
1. Drag **Text** element to the top
2. Set text: `🎯 SALES COACH`
3. Make it bold/large (Heading 1)

### 2.3 Add Filter Bar
1. Drag **Filter** element below header
2. Configure filters for:
   - **Primary Stage** (dropdown)
   - **Influencer** (dropdown)
   - **Keywords** (text search)

### 2.4 Add Gallery View
1. Drag **Gallery** element as main content
2. Configure cards to show:
   - **Title**: Key Insight
   - **Subtitle**: Influencer
   - **Caption**: Primary Stage
3. Set card size to Medium
4. Enable "Show record details on click"

### 2.5 Configure Record Detail View
When a card is clicked, show:
- Key Insight (full text)
- Tactical Steps
- Situation Examples
- Best Quote
- Source URL (as clickable link)

### 2.6 Publish
1. Click **Publish** in top right
2. Choose access level (private or shared link)
3. Copy the interface URL for easy access

---

## Step 3: "Ask the Coach" Q&A Tools

Since Airtable's Scripting extension requires a paid plan, we provide two free alternatives:

### Option A: CLI Tool (Quick & Local)

Run from terminal:
```bash
./run.sh ask_coach
```

Example session:
```
==================================================
ASK THE COACH - Sales Wisdom Q&A
==================================================

Describe your sales situation or question:
> I'm meeting with a skeptical CFO tomorrow

Searching knowledge base...
Found 127 total records
Found 5 relevant insights

Synthesizing coaching advice...

==================================================
COACHING ADVICE
==================================================

[Personalized advice with source attribution]
```

### Option B: Streamlit Web App (Best for Demos)

**Run locally:**
```bash
streamlit run streamlit_app.py
```
Opens at http://localhost:8501

**Deploy to Streamlit Cloud (free):**
1. Push your repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app" → Select your repo
4. Set main file to `streamlit_app.py`
5. Add secrets in App Settings → Secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   AIRTABLE_API_KEY = "pat..."
   AIRTABLE_BASE_ID = "app..."
   AIRTABLE_TABLE_NAME = "Sales Wisdom"
   ```

Your app will be live at `https://your-app.streamlit.app`

---

## Step 4: Usage Tips

### Good Questions to Ask
- "I'm in discovery with a CFO who seems distracted. What should I do?"
- "The procurement team is pushing back on pricing. How do I respond?"
- "How do I create urgency without being pushy?"
- "What questions should I ask to uncover the real decision maker?"
- "The prospect went silent after my demo. How do I follow up?"

### Browsing Tips (Airtable Interface)
- Use **Primary Stage** filter to focus on specific deal phases
- Search **Keywords** for topics like "objection", "cold call", "email"
- Click cards to see full tactical steps and source links

---

## Troubleshooting

### "No Matches Found"
- Try broader keywords
- Check that data has been imported (`push_airtable.py`)
- Verify table name is exactly "Sales Wisdom"

### API Errors
- Verify API key is correctly configured
- Check you have API credits at [console.anthropic.com](https://console.anthropic.com)
- For Streamlit Cloud: verify secrets are in App Settings

### Streamlit Won't Start
- Install dependencies: `pip install -r requirements.txt`
- Check Python version (3.10+ required)

---

## Demo Script

For demoing the Sales Coach (e.g., in a job interview):

1. **Show the Airtable Interface**
   - "This is a browsable library of sales wisdom, collected automatically from top sales voices on LinkedIn and YouTube"
   - Filter by "Discovery" stage
   - Click a card to show detailed insights

2. **Run Ask the Coach (Streamlit)**
   - "But the real power is natural language Q&A"
   - Open the Streamlit app
   - Ask: "I'm meeting with a skeptical CFO tomorrow. What should I focus on?"
   - Show how it synthesizes advice from multiple experts

3. **Highlight the Stack**
   - "Data pipeline runs weekly via GitHub Actions"
   - "Claude API processes and categorizes content"
   - "Airtable stores the data, Streamlit provides the Q&A interface"
   - "This is the kind of creative problem-solving I bring to customer conversations"

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                        SALES COACH                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA PIPELINE (Weekly/Automated)                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ LinkedIn │ → │ Claude   │ → │ Process  │ → │ Airtable │     │
│  │ YouTube  │   │ Analysis │   │ & Score  │   │ Storage  │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AIRTABLE INTERFACE (Browse Mode)                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Filter: [Stage ▼] [Influencer ▼] [Keyword 🔍]          │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ Gallery View → Click for full details + source link     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ASK THE COACH (CLI or Streamlit)                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ User Question → Keyword Match → Claude Synthesis        │   │
│  │ → Personalized Advice with Source Attribution           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
