#!/usr/bin/env python3
"""
Persona Generation Pipeline — Claude Batch API

Aggregates content per expert from Airtable records (and optionally
raw .tmp/ files), analyzes voice/style/frameworks via Claude Sonnet,
and writes structured persona profiles to data/personas.json.

Usage:
    python tools/generate_personas.py              # generate all
    python tools/generate_personas.py --dry-run    # show what would be generated
    python tools/generate_personas.py --expert chris-voss  # single expert

Input:
    - Airtable records (primary source: processed insights)
    - data/influencers.json (metadata, focus areas)
    - .tmp/youtube_raw.json (optional: raw transcripts for richer analysis)
    - .tmp/linkedin_raw.json (optional: raw posts)

Output:
    data/personas.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime

import anthropic
from pyairtable import Api

from config import (
    ANTHROPIC_API_KEY,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    TMP_DIR,
    DEAL_STAGES,
    PERSONAS_PATH,
    INFLUENCERS_PATH,
    PERSONA_CLAUDE_MODEL,
    PERSONA_MAX_TOKENS,
    PERSONA_TEMPERATURE,
    PERSONA_POLL_INTERVAL,
    PERSONA_HIGH_INSIGHTS,
    PERSONA_HIGH_CHARS,
    PERSONA_MEDIUM_INSIGHTS,
    PERSONA_MEDIUM_CHARS,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# File paths for optional raw content
YOUTUBE_RAW = TMP_DIR / "youtube_raw.json"
LINKEDIN_RAW = TMP_DIR / "linkedin_raw.json"


# ──────────────────────────────────────────────
# Analysis Prompt
# ──────────────────────────────────────────────

PERSONA_ANALYSIS_PROMPT = """You are analyzing the teaching style, voice, and methodology of a sales expert to build an AI persona profile.

== EXPERT ==
Name: {name}
Known for: {notes}
Focus areas: {focus_areas}

== THEIR CONTENT SAMPLES ==

{content_samples}

== THEIR KEY QUOTES (from processed insights) ==
{quotes}

== THEIR KEYWORDS (aggregated) ==
{keywords}

== TASK ==
Analyze this expert's communication style, frameworks, and signature patterns.
Respond in JSON only (no markdown fences, no explanation):

{{
  "voice_profile": {{
    "communication_style": "2-3 sentences describing how they communicate (e.g., direct, storytelling, data-driven)",
    "tone": "Key tonal qualities (e.g., calm and confident, energetic and challenging)",
    "vocabulary_level": "Their vocabulary register (e.g., accessible but specialized, academic, casual)",
    "sentence_structure": "How they construct sentences (e.g., short punchy statements, complex arguments)",
    "teaching_approach": "How they teach concepts (e.g., through anecdotes, through frameworks, through challenges)"
  }},
  "signature_frameworks": [
    {{
      "name": "Framework Name",
      "description": "What it is and how it works (1-2 sentences)",
      "typical_usage": "When/how the expert typically introduces this"
    }}
  ],
  "signature_phrases": ["Direct quotes or characteristic phrasings they use repeatedly"],
  "key_topics": ["5-8 core topics they focus on"],
  "deal_stage_strengths": ["2-4 deal stages from this list where they are strongest: {stages}"],
  "suggested_questions": [
    "4 natural questions a salesperson would ask this expert, phrased conversationally"
  ],
  "sample_response_pattern": "2-3 sentences describing how this expert typically structures a response to a question"
}}

IMPORTANT:
- signature_frameworks: Include 2-6 frameworks. Only include frameworks the expert actually teaches, not generic sales concepts.
- signature_phrases: Include 3-8 direct quotes or characteristic phrasings from the content.
- deal_stage_strengths: Use ONLY stages from the provided list. Pick stages where their content is strongest.
- suggested_questions: Make these specific to the expert's methodology, not generic sales questions."""


# ──────────────────────────────────────────────
# Data Aggregation
# ──────────────────────────────────────────────

def load_influencers() -> dict:
    """Load influencer registry, return dict keyed by name."""
    with open(INFLUENCERS_PATH) as f:
        data = json.load(f)
    return {
        i["name"]: i
        for i in data["influencers"]
        if i["status"] == "active"
    }


def fetch_airtable_records() -> list[dict]:
    """Fetch all records from Airtable."""
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        logger.error("Airtable credentials not configured")
        sys.exit(1)

    base_id = AIRTABLE_BASE_ID.split("/")[0]
    api = Api(AIRTABLE_API_KEY)
    table = api.table(base_id, AIRTABLE_TABLE_NAME)
    records = table.all()
    logger.info(f"Fetched {len(records)} records from Airtable")
    return records


def load_raw_content() -> dict:
    """Load optional raw content from .tmp/, grouped by influencer name.

    Returns:
        Dict mapping influencer name -> {"youtube_chunks": [...], "linkedin_posts": [...]}
    """
    raw = {}

    if YOUTUBE_RAW.exists():
        with open(YOUTUBE_RAW) as f:
            data = json.load(f)
        for video in data.get("videos", []):
            name = video.get("influencer", "")
            if name not in raw:
                raw[name] = {"youtube_chunks": [], "linkedin_posts": []}
            for chunk in video.get("transcript_chunks", []):
                raw[name]["youtube_chunks"].append(chunk.get("content", ""))
        logger.info(f"Loaded raw YouTube content for {len(raw)} experts")

    if LINKEDIN_RAW.exists():
        with open(LINKEDIN_RAW) as f:
            data = json.load(f)
        for post in data.get("posts", []):
            name = post.get("influencer", "")
            if name not in raw:
                raw[name] = {"youtube_chunks": [], "linkedin_posts": []}
            raw[name]["linkedin_posts"].append(post.get("content", ""))
        logger.info(f"Loaded raw LinkedIn content")

    return raw


def aggregate_per_expert(
    records: list[dict],
    influencers: dict,
    raw_content: dict,
) -> list[dict]:
    """Aggregate all available data per expert for persona analysis.

    Returns:
        List of dicts, each containing an expert's aggregated content
        ready for the analysis prompt.
    """
    # Group Airtable records by influencer name
    by_name: dict[str, list[dict]] = {}
    for record in records:
        fields = record.get("fields", {})
        name = fields.get("Influencer", "")
        if name:
            by_name.setdefault(name, []).append(fields)

    experts = []
    for name, inf in influencers.items():
        slug = inf["slug"]
        meta = inf.get("metadata", {})
        notes = meta.get("notes", "")
        focus_areas = meta.get("focus_areas", [])

        insight_records = by_name.get(name, [])
        raw = raw_content.get(name, {"youtube_chunks": [], "linkedin_posts": []})

        # Collect quotes and keywords from processed insights
        quotes = []
        all_keywords = set()
        for rec in insight_records:
            quote = rec.get("Best Quote", "")
            if quote:
                quotes.append(quote)
            kw_str = rec.get("Keywords", "")
            if kw_str:
                for kw in kw_str.split(","):
                    kw = kw.strip()
                    if kw:
                        all_keywords.add(kw)

        # Build content samples string
        content_samples = _build_content_samples(
            insight_records, raw["youtube_chunks"], raw["linkedin_posts"]
        )

        # Estimate total source chars for confidence scoring
        total_chars = sum(len(c) for c in raw["youtube_chunks"])
        total_chars += sum(len(p) for p in raw["linkedin_posts"])
        # Also count insight text as source material
        for rec in insight_records:
            total_chars += len(rec.get("Key Insight", ""))
            total_chars += len(rec.get("Tactical Steps", ""))
            total_chars += len(rec.get("Best Quote", ""))

        experts.append({
            "slug": slug,
            "name": name,
            "notes": notes,
            "focus_areas": focus_areas,
            "insight_count": len(insight_records),
            "total_source_chars": total_chars,
            "youtube_count": len(raw["youtube_chunks"]),
            "linkedin_count": len(raw["linkedin_posts"]),
            "content_samples": content_samples,
            "quotes": quotes,
            "keywords": sorted(all_keywords),
        })

    return experts


def _build_content_samples(
    insights: list[dict],
    youtube_chunks: list[str],
    linkedin_posts: list[str],
) -> str:
    """Build a representative content sample for the analysis prompt.

    Prioritizes raw content (richer signal), falls back to processed insights.
    Caps total at ~6000 chars to stay within prompt budget.
    """
    parts = []
    char_budget = 6000

    # YouTube transcript chunks (up to 3, prioritize longest)
    if youtube_chunks:
        sorted_yt = sorted(youtube_chunks, key=len, reverse=True)
        for chunk in sorted_yt[:3]:
            sample = chunk[:2500]
            parts.append(f"[YouTube transcript excerpt]\n{sample}")
            char_budget -= len(sample)
            if char_budget <= 0:
                break

    # LinkedIn posts (up to 5, prioritize longer)
    if linkedin_posts and char_budget > 0:
        sorted_li = sorted(linkedin_posts, key=len, reverse=True)
        for post in sorted_li[:5]:
            sample = post[:1000]
            parts.append(f"[LinkedIn post]\n{sample}")
            char_budget -= len(sample)
            if char_budget <= 0:
                break

    # Fall back to processed insights if no raw content
    if not parts and insights:
        for rec in insights[:8]:
            insight = rec.get("Key Insight", "")
            steps = rec.get("Tactical Steps", "")
            quote = rec.get("Best Quote", "")
            stage = rec.get("Primary Stage", "")
            sample = f"[Processed insight — {stage}]\n"
            if insight:
                sample += f"Insight: {insight}\n"
            if steps:
                sample += f"Steps: {steps}\n"
            if quote:
                sample += f'Quote: "{quote}"\n'
            parts.append(sample)
            char_budget -= len(sample)
            if char_budget <= 0:
                break

    return "\n\n".join(parts) if parts else "(No content samples available)"


# ──────────────────────────────────────────────
# Confidence Scoring
# ──────────────────────────────────────────────

def compute_confidence(insight_count: int, total_chars: int) -> str:
    """Determine confidence level based on data density."""
    if insight_count >= PERSONA_HIGH_INSIGHTS and total_chars >= PERSONA_HIGH_CHARS:
        return "high"
    if insight_count >= PERSONA_MEDIUM_INSIGHTS or total_chars >= PERSONA_MEDIUM_CHARS:
        return "medium"
    return "low"


# ──────────────────────────────────────────────
# Batch API
# ──────────────────────────────────────────────

def build_batch_requests(experts: list[dict]) -> list[dict]:
    """Build Batch API requests for persona analysis."""
    requests = []
    for expert in experts:
        prompt = PERSONA_ANALYSIS_PROMPT.format(
            name=expert["name"],
            notes=expert["notes"],
            focus_areas=", ".join(expert["focus_areas"]),
            content_samples=expert["content_samples"],
            quotes="\n".join(f'- "{q}"' for q in expert["quotes"][:15]),
            keywords=", ".join(expert["keywords"][:30]),
            stages=", ".join(DEAL_STAGES),
        )
        requests.append({
            "custom_id": expert["slug"],
            "params": {
                "model": PERSONA_CLAUDE_MODEL,
                "max_tokens": PERSONA_MAX_TOKENS,
                "temperature": PERSONA_TEMPERATURE,
                "messages": [{"role": "user", "content": prompt}],
            },
        })
    return requests


def run_batch(client: anthropic.Anthropic, requests: list[dict]) -> dict:
    """Submit batch, poll for completion, return results keyed by custom_id."""
    logger.info(f"Submitting batch of {len(requests)} persona analysis requests...")

    batch = client.messages.batches.create(requests=requests)
    logger.info(f"Batch created: {batch.id} (status: {batch.processing_status})")

    # Poll for completion
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        logger.info(
            f"Batch {batch.id}: {batch.processing_status} "
            f"({done}/{total} done, {counts.succeeded} ok, {counts.errored} err)"
        )
        if batch.processing_status == "ended":
            break
        time.sleep(PERSONA_POLL_INTERVAL)

    # Collect results
    results = {}
    errors = 0
    for entry in client.messages.batches.results(batch.id):
        if entry.result.type != "succeeded":
            errors += 1
            logger.warning(f"Failed: {entry.custom_id} ({entry.result.type})")
            continue

        try:
            text = entry.result.message.content[0].text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            results[entry.custom_id] = json.loads(text)
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            errors += 1
            logger.warning(f"Parse error for {entry.custom_id}: {e}")

    logger.info(f"Batch complete: {len(results)} succeeded, {errors} errors")
    return results


# ──────────────────────────────────────────────
# Assembly & Output
# ──────────────────────────────────────────────

def assemble_personas(experts: list[dict], analysis_results: dict) -> list[dict]:
    """Combine aggregated data with Claude analysis into final persona objects."""
    personas = []
    for expert in experts:
        slug = expert["slug"]
        analysis = analysis_results.get(slug)
        if not analysis:
            logger.warning(f"No analysis result for {expert['name']}, skipping")
            continue

        confidence = compute_confidence(
            expert["insight_count"], expert["total_source_chars"]
        )

        persona = {
            "slug": slug,
            "name": expert["name"],
            "persona_version": 1,
            "generated_at": datetime.now().isoformat(),
            "data_basis": {
                "linkedin_posts": expert["linkedin_count"],
                "youtube_transcripts": expert["youtube_count"],
                "total_insights": expert["insight_count"],
                "total_source_chars": expert["total_source_chars"],
            },
            "confidence": confidence,
            "voice_profile": analysis.get("voice_profile", {}),
            "signature_frameworks": analysis.get("signature_frameworks", []),
            "signature_phrases": analysis.get("signature_phrases", []),
            "key_topics": analysis.get("key_topics", []),
            "deal_stage_strengths": _validate_stages(
                analysis.get("deal_stage_strengths", [])
            ),
            "suggested_questions": analysis.get("suggested_questions", []),
            "sample_response_pattern": analysis.get("sample_response_pattern", ""),
        }
        personas.append(persona)

    return personas


def _validate_stages(stages: list[str]) -> list[str]:
    """Filter deal stages to only valid values."""
    valid = set(DEAL_STAGES)
    validated = [s for s in stages if s in valid]
    if len(validated) < len(stages):
        invalid = [s for s in stages if s not in valid]
        logger.warning(f"Removed invalid deal stages: {invalid}")
    return validated


def write_personas(personas: list[dict]) -> None:
    """Write personas to data/personas.json."""
    PERSONAS_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_personas": len(personas),
        "personas": sorted(personas, key=lambda p: p["name"]),
    }

    with open(PERSONAS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Wrote {len(personas)} personas to {PERSONAS_PATH}")


def print_coverage_report(experts: list[dict], personas: list[dict]) -> None:
    """Print a data coverage summary."""
    persona_slugs = {p["slug"] for p in personas}

    print("\n" + "=" * 70)
    print("PERSONA COVERAGE REPORT")
    print("=" * 70)

    by_confidence = {"high": [], "medium": [], "low": []}
    for expert in sorted(experts, key=lambda e: e["total_source_chars"], reverse=True):
        confidence = compute_confidence(
            expert["insight_count"], expert["total_source_chars"]
        )
        status = "OK" if expert["slug"] in persona_slugs else "MISSING"
        by_confidence[confidence].append((expert, status))

    for level in ("high", "medium", "low"):
        items = by_confidence[level]
        print(f"\n{level.upper()} confidence ({len(items)} experts):")
        for expert, status in items:
            chars = expert["total_source_chars"]
            insights = expert["insight_count"]
            chars_display = f"{chars // 1000}K" if chars >= 1000 else f"{chars}"
            print(
                f"  [{status:>7}] {expert['name']:<25} "
                f"{insights:>3} insights, {chars_display:>5} chars"
            )

    print(f"\nTotal: {len(personas)}/{len(experts)} personas generated")
    print("=" * 70)


# ──────────────────────────────────────────────
# Voice Fidelity Validation
# ──────────────────────────────────────────────

def validate_personas(client: anthropic.Anthropic, n: int = 3) -> None:
    """Spot-check persona voice fidelity.

    Picks n random high-confidence personas, sends a test question,
    and checks that the response references frameworks and phrases.
    """
    import random
    from personas import load_personas, build_persona_system_prompt, load_influencer_meta

    personas = load_personas()
    influencer_meta = load_influencer_meta()

    if not personas:
        logger.error("No personas found — run generation first")
        sys.exit(1)

    high = [p for p in personas.values() if p["confidence"] == "high"]
    if not high:
        logger.warning("No high-confidence personas, checking medium")
        high = [p for p in personas.values() if p["confidence"] == "medium"]

    samples = random.sample(high, min(n, len(high)))

    test_question = "A prospect just told me they need to think about it. What should I do?"

    print("\n" + "=" * 70)
    print("VOICE FIDELITY VALIDATION")
    print("=" * 70)

    all_passed = True
    for persona in samples:
        name = persona["name"]
        slug = persona["slug"]
        frameworks = [fw["name"].lower() for fw in persona.get("signature_frameworks", [])]
        phrases = [p.lower() for p in persona.get("signature_phrases", [])]

        # Build prompt with minimal context
        context = "(No specific records — respond from your general expertise and frameworks.)"
        meta = influencer_meta.get(slug)
        system_prompt = build_persona_system_prompt(persona, context, meta)

        logger.info(f"Testing {name}...")
        response = client.messages.create(
            model=PERSONA_CLAUDE_MODEL,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": test_question}],
        )
        text = response.content[0].text.lower()

        # Check for framework mentions (word-level: match any significant
        # word from a framework name, since descriptive names like
        # "Buyer Enablement Over Sales Process" won't appear verbatim)
        stop_words = {"the", "and", "for", "over", "with", "from", "into", "based"}
        fw_hits = []
        for fw in frameworks:
            fw_words = [w for w in fw.split() if len(w) > 3 and w not in stop_words]
            if any(w in text for w in fw_words):
                fw_hits.append(fw)

        # Exact phrase matches (these are short coined phrases)
        phrase_hits = [p for p in phrases if p in text]

        # First-person voice
        first_person = any(marker in text for marker in ["i ", "my ", "i've ", "i'm "])

        # Key topics mentioned (backup signal for framework relevance)
        topics = [t.lower() for t in persona.get("key_topics", [])]
        topic_hits = [t for t in topics if t in text]

        passed = (len(fw_hits) > 0 or len(topic_hits) >= 2) and first_person
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False

        print(f"\n[{status}] {name} ({persona['confidence']})")
        print(f"  Frameworks referenced: {fw_hits if fw_hits else 'NONE'} (of {len(frameworks)})")
        print(f"  Topics referenced:     {len(topic_hits)}/{len(topics)} ({', '.join(topic_hits[:4])})")
        print(f"  Phrases echoed:        {len(phrase_hits)} (of {len(phrases)})")
        print(f"  First-person voice:    {'Yes' if first_person else 'No'}")
        if not passed:
            print(f"  Response preview:      {response.content[0].text[:200]}...")

    print(f"\n{'All checks passed!' if all_passed else 'Some checks failed — review above.'}")
    print("=" * 70)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate AI persona profiles")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be generated without calling Claude API"
    )
    parser.add_argument(
        "--expert", type=str, default=None,
        help="Generate persona for a single expert (slug, e.g., chris-voss)"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Spot-check voice fidelity of 3 random high-confidence personas"
    )
    args = parser.parse_args()

    # Validation mode: doesn't need Airtable, just personas.json + Claude
    if args.validate:
        if not ANTHROPIC_API_KEY:
            logger.error("ANTHROPIC_API_KEY not set")
            sys.exit(1)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        validate_personas(client)
        return

    logger.info("Starting persona generation pipeline...")

    # 1. Load data sources
    influencers = load_influencers()
    logger.info(f"Loaded {len(influencers)} active influencers from registry")

    records = fetch_airtable_records()
    raw_content = load_raw_content()

    # 2. Aggregate per expert
    experts = aggregate_per_expert(records, influencers, raw_content)
    logger.info(f"Aggregated content for {len(experts)} experts")

    # Filter to single expert if requested
    if args.expert:
        experts = [e for e in experts if e["slug"] == args.expert]
        if not experts:
            logger.error(f"Expert '{args.expert}' not found")
            sys.exit(1)
        logger.info(f"Filtered to single expert: {experts[0]['name']}")

    # 3. Dry-run mode: show coverage and exit
    if args.dry_run:
        print_coverage_report(experts, [])

        # Estimate cost (Sonnet Batch: input $1.50/MTok, output $7.50/MTok)
        total_prompt_chars = sum(len(e["content_samples"]) for e in experts)
        est_input = total_prompt_chars // 4 + len(experts) * 500  # prompt overhead
        est_output = len(experts) * 1500
        est_cost = (est_input * 1.50 + est_output * 7.50) / 1_000_000
        print(f"\nEstimated Batch API cost: ${est_cost:.2f}")
        print(f"  ~{est_input:,} input tokens + ~{est_output:,} output tokens")
        print(f"  Model: {PERSONA_CLAUDE_MODEL}")
        return

    # 4. Run Claude Batch API
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    batch_requests = build_batch_requests(experts)
    analysis_results = run_batch(client, batch_requests)

    # 5. Assemble and write
    personas = assemble_personas(experts, analysis_results)
    write_personas(personas)

    # 6. Report
    print_coverage_report(experts, personas)


if __name__ == "__main__":
    main()
