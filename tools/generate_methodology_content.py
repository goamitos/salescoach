#!/usr/bin/env python3
"""
Generate rich methodology content using Claude API.

Reads skeleton methodology data from the database, sends one prompt per
methodology to Claude, and writes the generated content as JSON files
to .tmp/methodologies/ for human review before DB insertion.

Usage:
    python generate_methodology_content.py              # Generate all
    python generate_methodology_content.py meddic spin  # Generate specific ones
    python generate_methodology_content.py --list       # Show what exists

Output:
    .tmp/methodologies/meddic.json
    .tmp/methodologies/challenger.json
    ...

Cost estimate: ~10 calls × ~3K output tokens ≈ $0.05 with Sonnet
"""

import json
import logging
import sys
import time
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, TMP_DIR, RATE_LIMIT_CLAUDE
from db import get_connection, init_db, get_methodology_tree

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = TMP_DIR / "methodologies"
OUTPUT_DIR.mkdir(exist_ok=True)

GENERATION_PROMPT = """You are a sales methodology expert. Generate detailed, practical content for the **{name}** sales methodology.

METHODOLOGY CONTEXT:
- Name: {name}
- Author: {author}
- Source: {source}
- Category: {category}

COMPONENTS (generate content for each):
{components_list}

Respond in JSON format only (no markdown fences, no explanation). Use this exact structure:

{{
  "overview": "2-3 paragraphs explaining what {name} is, its history, and why it matters in modern sales. Be specific and practical, not generic.",
  "core_philosophy": "The fundamental idea in 1-2 sentences — what makes this methodology distinct.",
  "when_to_use": "Specific deal types, org sizes, selling motions, and buyer personas where this works best. Include where it does NOT work well.",
  "strengths": "3-4 concrete strengths with brief explanations.",
  "limitations": "2-3 honest limitations or common criticisms.",
  "components": {{
    "{first_component_id}": {{
      "description": "2-3 sentences: what this component is and why it matters in the sales process.",
      "how_to_execute": "3-5 concrete techniques, questions to ask, or steps to take. Be specific enough that a rep could use this tomorrow.",
      "common_mistakes": "2-3 anti-patterns or pitfalls practitioners fall into.",
      "example_scenario": "A realistic enterprise deal scenario (named company optional) illustrating this component in action. 3-5 sentences."
    }}
  }}
}}

IMPORTANT:
- Write for experienced salespeople, not beginners. Skip obvious basics.
- Include specific questions reps can ask, not just abstract concepts.
- Example scenarios should feel like real deals, not textbook examples.
- Each component's content should be distinct — avoid repeating the same advice across components.
"""


def build_prompt(methodology: dict) -> str:
    """Build the generation prompt for a single methodology."""
    components = methodology["components"]
    components_list = "\n".join(
        f"- {c['name']}" + (f" [{c['abbreviation']}]" if c['abbreviation'] else "")
        + f" (id: {c['id']}): Keywords: {c['keywords']}"
        for c in components
    )

    # Show the expected JSON keys for all components
    first_id = components[0]["id"] if components else "component_id"

    prompt = GENERATION_PROMPT.format(
        name=methodology["name"],
        author=methodology["author"] or "Unknown",
        source=methodology["source"] or "Unknown",
        category=methodology["category"] or "general",
        components_list=components_list,
        first_component_id=first_id,
    )

    # Add note about all component IDs expected
    if len(components) > 1:
        all_ids = ", ".join(f'"{c["id"]}"' for c in components)
        prompt += f"\n\nGenerate content for ALL component IDs: {all_ids}"

    return prompt


def generate_content(client: anthropic.Anthropic, methodology: dict) -> dict:
    """Call Claude API to generate content for one methodology."""
    prompt = build_prompt(methodology)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Handle potential markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    return json.loads(text)


def generate_all(methodology_ids: Optional[list[str]] = None) -> None:
    """Generate content for all (or specified) methodologies."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set. Run via ./run.sh or set in .env")
        return

    init_db()
    conn = get_connection()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        tree = get_methodology_tree(conn)

        if methodology_ids:
            tree = [m for m in tree if m["id"] in methodology_ids]
            if not tree:
                logger.error("No matching methodologies found for: %s", methodology_ids)
                return

        total = len(tree)
        logger.info("Generating content for %d methodologies", total)

        for i, methodology in enumerate(tree, 1):
            mid = methodology["id"]
            output_path = OUTPUT_DIR / f"{mid}.json"

            # Skip if already generated (use --force to regenerate)
            if output_path.exists() and "--force" not in sys.argv:
                logger.info("[%d/%d] Skipping %s (already exists, use --force to regenerate)", i, total, mid)
                continue

            logger.info("[%d/%d] Generating content for %s...", i, total, methodology["name"])

            try:
                content = generate_content(client, methodology)

                # Merge skeleton data with generated content
                output = {
                    "id": mid,
                    "name": methodology["name"],
                    "author": methodology["author"],
                    "source": methodology["source"],
                    "category": methodology["category"],
                    "deal_stages": json.loads(methodology["deal_stages"]) if methodology["deal_stages"] else [],
                    # Generated fields
                    "overview": content.get("overview", ""),
                    "core_philosophy": content.get("core_philosophy", ""),
                    "when_to_use": content.get("when_to_use", ""),
                    "strengths": content.get("strengths", ""),
                    "limitations": content.get("limitations", ""),
                    "components": [],
                }

                # Merge component content
                generated_components = content.get("components", {})
                for comp in methodology["components"]:
                    cid = comp["id"]
                    gen = generated_components.get(cid, {})
                    output["components"].append({
                        "id": cid,
                        "name": comp["name"],
                        "abbreviation": comp["abbreviation"],
                        "sequence_order": comp["sequence_order"],
                        "keywords": json.loads(comp["keywords"]) if isinstance(comp["keywords"], str) else comp["keywords"],
                        # Generated fields
                        "description": gen.get("description", ""),
                        "how_to_execute": gen.get("how_to_execute", ""),
                        "common_mistakes": gen.get("common_mistakes", ""),
                        "example_scenario": gen.get("example_scenario", ""),
                    })

                with open(output_path, "w") as f:
                    json.dump(output, f, indent=2)

                logger.info("[%d/%d] Wrote %s", i, total, output_path.name)

            except (json.JSONDecodeError, KeyError) as e:
                logger.error("[%d/%d] Failed to parse response for %s: %s", i, total, mid, e)
                continue
            except anthropic.APIError as e:
                logger.error("[%d/%d] API error for %s: %s", i, total, mid, e)
                continue

            # Rate limit between calls
            if i < total:
                time.sleep(RATE_LIMIT_CLAUDE)

        # Summary
        generated = list(OUTPUT_DIR.glob("*.json"))
        print("=" * 50)
        print("CONTENT GENERATION COMPLETE")
        print("=" * 50)
        print(f"  Output dir: {OUTPUT_DIR}")
        print(f"  Files: {len(generated)}")
        for f in sorted(generated):
            size = f.stat().st_size
            print(f"    {f.name} ({size:,} bytes)")
        print("=" * 50)
        print()
        print("Next: Review the JSON files, then run Step 3 to insert into DB.")

    finally:
        conn.close()


def list_existing() -> None:
    """Show what's already been generated."""
    generated = list(OUTPUT_DIR.glob("*.json"))
    if not generated:
        print("No generated files yet. Run without --list to generate.")
        return
    print(f"Generated files in {OUTPUT_DIR}:")
    for f in sorted(generated):
        with open(f) as fh:
            data = json.load(fh)
        n_components = len(data.get("components", []))
        has_content = bool(data.get("overview"))
        status = "has content" if has_content else "skeleton only"
        print(f"  {f.name}: {n_components} components ({status})")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_existing()
    else:
        # Filter specific methodology IDs if provided
        ids = [a for a in sys.argv[1:] if not a.startswith("-")]
        generate_all(ids or None)
