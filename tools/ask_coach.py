#!/usr/bin/env python3
"""
Ask the Coach - CLI Sales Wisdom Q&A

Takes a natural language question about sales situations,
searches the Airtable knowledge base, and uses Claude to
synthesize personalized coaching advice.

Usage:
    python tools/ask_coach.py
    # or via run.sh:
    ./run.sh ask_coach

Requires:
    - ANTHROPIC_API_KEY
    - AIRTABLE_API_KEY
    - AIRTABLE_BASE_ID
    - AIRTABLE_TABLE_NAME
"""
import re
import sys
from pyairtable import Api
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    CLAUDE_MODEL,
)

# Stage-related keywords for better matching
STAGE_KEYWORDS = {
    "discovery": [
        "discovery",
        "discover",
        "question",
        "ask",
        "learn",
        "understand",
        "needs",
    ],
    "prospecting": ["prospect", "cold", "outreach", "email", "call", "reach", "sdr"],
    "negotiation": [
        "negotiate",
        "negotiation",
        "price",
        "pricing",
        "discount",
        "contract",
    ],
    "closing": ["close", "closing", "deal", "sign", "commit", "decision", "won"],
    "objection": ["objection", "pushback", "concern", "hesitation", "resist", "but"],
    "demo": ["demo", "presentation", "present", "show", "demonstrate"],
    "qualification": [
        "qualify",
        "qualification",
        "fit",
        "budget",
        "authority",
        "timeline",
        "bant",
    ],
    "followup": ["follow", "followup", "silent", "ghost", "respond", "reply"],
}


def fetch_records():
    """Fetch all records from Airtable."""
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("Error: Airtable credentials not configured")
        sys.exit(1)

    base_id = AIRTABLE_BASE_ID.split("/")[0]
    api = Api(AIRTABLE_API_KEY)
    table = api.table(base_id, AIRTABLE_TABLE_NAME)

    records = table.all()
    return records


def score_record(
    record: dict, user_keywords: list[str], matched_stages: list[str]
) -> float:
    """Score a record based on keyword and stage matches."""
    fields = record.get("fields", {})

    insight = (fields.get("Key Insight") or "").lower()
    stage = (fields.get("Primary Stage") or "").lower()
    secondary = (fields.get("Secondary Stages") or "").lower()
    steps = (fields.get("Tactical Steps") or "").lower()
    keywords = (fields.get("Keywords") or "").lower()
    situations = (fields.get("Situation Examples") or "").lower()
    quote = (fields.get("Best Quote") or "").lower()

    combined = f"{insight} {stage} {secondary} {steps} {keywords} {situations} {quote}"

    score = 0.0

    # Score based on keyword matches
    for kw in user_keywords:
        if kw in combined:
            score += 2

    # Bonus for stage matches
    for matched_stage in matched_stages:
        if matched_stage in stage or matched_stage in secondary:
            score += 3

    # Boost for higher original relevance scores
    original_score = fields.get("Relevance Score") or 0
    score += original_score / 5

    return score


def find_relevant_records(
    records: list[dict], scenario: str, top_n: int = 5
) -> list[dict]:
    """Find the most relevant records for a given scenario."""
    # Extract keywords from user's question
    user_keywords = [
        word.lower() for word in re.findall(r"\w+", scenario) if len(word) > 3
    ]

    # Find stage matches
    matched_stages = []
    scenario_lower = scenario.lower()
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(kw in scenario_lower for kw in keywords):
            matched_stages.append(stage)

    # Score all records
    scored = []
    for record in records:
        score = score_record(record, user_keywords, matched_stages)
        if score > 0:
            scored.append((record, score))

    # Sort by score and return top N
    scored.sort(key=lambda x: x[1], reverse=True)
    return [record for record, _ in scored[:top_n]]


def build_context(records: list[dict]) -> str:
    """Build context string from relevant records."""
    parts = []
    for record in records:
        fields = record.get("fields", {})
        influencer = fields.get("Influencer") or "Unknown"
        stage = fields.get("Primary Stage") or "General"
        insight = fields.get("Key Insight") or ""
        steps = fields.get("Tactical Steps") or ""
        situations = fields.get("Situation Examples") or ""
        quote = fields.get("Best Quote") or ""

        part = f"**{influencer}** ({stage}):\nInsight: {insight}"
        if steps:
            part += f"\nSteps: {steps}"
        if situations:
            part += f"\nWhen to use: {situations}"
        if quote:
            part += f'\nKey quote: "{quote}"'
        parts.append(part)

    return "\n\n---\n\n".join(parts)


def get_coaching_advice(scenario: str, context: str) -> str:
    """Call Claude API to synthesize coaching advice."""
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not configured")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = """You are an expert sales coach who synthesizes wisdom from top sales leaders to provide actionable advice.

Your role is to:
1. Understand the salesperson's specific situation
2. Draw from the provided expert insights to craft personalized advice
3. Give concrete, actionable steps (not generic platitudes)
4. Reference which expert's approach you're drawing from
5. Keep advice focused and practical (3-5 key points)

Format your response with:
- A brief acknowledgment of their situation
- Numbered actionable recommendations
- Brief attribution to the relevant experts"""

    user_prompt = f"""A salesperson describes their situation:

"{scenario}"

Based on these expert insights from top sales leaders:

{context}

Provide specific, actionable coaching advice. Reference which expert's wisdom you're drawing from when relevant."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text


def print_sources(records: list[dict]):
    """Print source attribution."""
    print("\n" + "=" * 50)
    print("SOURCES USED")
    print("=" * 50)
    for record in records:
        fields = record.get("fields", {})
        influencer = fields.get("Influencer") or "Unknown"
        stage = fields.get("Primary Stage") or "General"
        url = fields.get("Source URL") or ""
        insight = fields.get("Key Insight") or ""

        # Truncate insight
        short_insight = insight[:80] + "..." if len(insight) > 80 else insight
        print(f"\n- {influencer} ({stage})")
        print(f"  {short_insight}")
        if url:
            print(f"  {url}")


def main():
    """Main function."""
    print("=" * 50)
    print("ASK THE COACH - Sales Wisdom Q&A")
    print("=" * 50)
    print()

    # Check for CLI argument first
    if len(sys.argv) > 1:
        scenario = " ".join(sys.argv[1:]).strip()
        print(f"Question: {scenario}")
        print()
    else:
        # Interactive mode (existing behavior)
        print("Describe your sales situation or question:")
        print("(Type your question and press Enter)")
        print()

        try:
            scenario = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

    if not scenario:
        print("No question provided. Exiting.")
        return

    print()
    print("Searching knowledge base...")

    # Fetch and search records
    records = fetch_records()
    print(f"Found {len(records)} total records")

    relevant = find_relevant_records(records, scenario)

    if not relevant:
        print("\nNo matching insights found. Try:")
        print("- Using different keywords")
        print("- Being more specific about the sales stage")
        print(
            "- Asking about: discovery, objections, closing, negotiation, prospecting"
        )
        return

    print(f"Found {len(relevant)} relevant insights")
    print()
    print("Synthesizing coaching advice...")
    print()

    # Get advice from Claude
    context = build_context(relevant)
    advice = get_coaching_advice(scenario, context)

    # Display results
    print("=" * 50)
    print("COACHING ADVICE")
    print("=" * 50)
    print()
    print(advice)

    # Print sources
    print_sources(relevant)

    print()
    print("-" * 50)
    print(f"Powered by Sales Coach AI - {len(records)} curated insights")


if __name__ == "__main__":
    main()
