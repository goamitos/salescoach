#!/usr/bin/env python3
"""
Search Leaders — VP/CRO Content Search & AI Q&A

Searches the VP Sales / CRO subset of the Sales Coach knowledge base.
Optionally synthesizes AI coaching advice from leadership-relevant insights.

Usage:
    python tools/search_leaders.py "pipeline review"
    python tools/search_leaders.py --ask "how to build a forecast process"
    python tools/search_leaders.py --stage Discovery "coaching reps"
    ./run.sh search_leaders "query"
    ./run.sh search_leaders --ask "question"
"""
import argparse
import json
import sys

import anthropic

from config import ANTHROPIC_API_KEY
from db import get_connection, search_leaders


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Search VP/CRO sales leadership content",
    )
    parser.add_argument("query", help="Search query or question")
    parser.add_argument(
        "--ask", action="store_true",
        help="AI synthesis mode: get a Claude-powered answer from VP/CRO content",
    )
    parser.add_argument("--stage", type=str, default=None, help="Filter by deal stage")
    parser.add_argument("--influencer", type=str, default=None, help="Filter by influencer name")
    parser.add_argument(
        "--min-confidence", type=float, default=0.7,
        help="Minimum audience confidence threshold (default: 0.7)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    return parser.parse_args(argv)


def display_results(results):
    """Print search results in readable format."""
    if not results:
        print("\nNo VP/CRO leadership content found for this query.")
        print("Try broader keywords or lower --min-confidence.")
        return

    print(f"\n{'='*60}")
    print(f"LEADERSHIP INSIGHTS ({len(results)} results)")
    print(f"{'='*60}")

    for i, r in enumerate(results, 1):
        audience = json.loads(r.get("target_audience") or "[]")
        confidence = r.get("audience_confidence", 0)
        print(f"\n--- [{i}] {r.get('influencer_name', 'Unknown')} ({r.get('primary_stage', 'General')}) ---")
        print(f"Audience: {', '.join(audience)} (confidence: {confidence:.0%})")
        print(f"Insight: {r.get('key_insight', '')}")

        steps = r.get("tactical_steps", "")
        if steps:
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except json.JSONDecodeError:
                    steps = [steps]
            if isinstance(steps, list):
                for step in steps:
                    print(f"  - {step}")

        quote = r.get("best_quote", "")
        if quote:
            print(f'  "{quote}"')

        url = r.get("source_url", "")
        if url:
            print(f"  Source: {url}")


def synthesize_answer(query, results):
    """Use Claude to synthesize an answer from VP/CRO results."""
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set — cannot synthesize.")
        return

    if not results:
        print("\nNo VP/CRO content to synthesize from.")
        return

    context_parts = []
    for r in results:
        name = r.get("influencer_name", "Unknown")
        stage = r.get("primary_stage", "General")
        insight = r.get("key_insight", "")
        steps = r.get("tactical_steps", "")
        quote = r.get("best_quote", "")
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                steps = [steps]
        steps_str = ", ".join(steps) if isinstance(steps, list) else str(steps)
        part = f"**{name}** ({stage}): {insight}"
        if steps_str:
            part += f"\nSteps: {steps_str}"
        if quote:
            part += f'\nQuote: "{quote}"'
        context_parts.append(part)

    context = "\n\n---\n\n".join(context_parts)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system = """You are a sales leadership coach specializing in advice for VP Sales and CRO roles.
You synthesize wisdom from top sales leaders to provide actionable advice for sales executives.
Focus on leadership, team management, strategy, and organizational decisions — not individual deal tactics.
Reference which expert's wisdom you're drawing from."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{
            "role": "user",
            "content": f'A sales leader asks:\n\n"{query}"\n\nBased on these leadership insights:\n\n{context}\n\nProvide specific, actionable advice for a VP Sales or CRO.',
        }],
    )

    print(f"\n{'='*60}")
    print("LEADERSHIP COACHING")
    print(f"{'='*60}\n")
    print(response.content[0].text)

    print(f"\n{'='*60}")
    print(f"Sources: {len(results)} VP/CRO insights used")
    print(f"{'='*60}")
    for r in results:
        name = r.get("influencer_name", "Unknown")
        insight = r.get("key_insight", "")[:80]
        print(f"  - {name}: {insight}...")


def main():
    args = parse_args()
    conn = get_connection()

    results = search_leaders(
        conn, args.query,
        limit=args.limit,
        stage=args.stage,
        min_confidence=args.min_confidence,
    )

    if args.influencer:
        results = [
            r for r in results
            if args.influencer.lower() in r.get("influencer_name", "").lower()
        ]

    if args.ask:
        synthesize_answer(args.query, results)
    else:
        display_results(results)

    conn.close()


if __name__ == "__main__":
    main()
