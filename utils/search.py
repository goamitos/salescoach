"""Record scoring and keyword matching for coaching queries."""
from __future__ import annotations

import re
from typing import Optional

# Stage-related keywords for matching user queries to stages
STAGE_KEYWORDS = {
    "discovery": ["discovery", "discover", "question", "ask", "learn", "understand", "needs"],
    "prospecting": ["prospect", "cold", "outreach", "email", "call", "reach", "sdr"],
    "negotiation": ["negotiate", "negotiation", "price", "pricing", "discount", "contract"],
    "closing": ["close", "closing", "deal", "sign", "commit", "decision", "won"],
    "objection": ["objection", "pushback", "concern", "hesitation", "resist", "but"],
    "demo": ["demo", "presentation", "present", "show", "demonstrate"],
    "qualification": ["qualify", "qualification", "fit", "budget", "authority", "timeline", "bant"],
    "followup": ["follow", "followup", "silent", "ghost", "respond", "reply"],
}


def score_insight(insight: dict, user_keywords: list[str], matched_stages: list[str]) -> float:
    """Score an insight based on keyword and stage matches."""
    combined = " ".join([
        insight.get("key_insight", ""),
        insight.get("primary_stage", ""),
        " ".join(insight.get("secondary_stages") or []),
        " ".join(insight.get("tactical_steps") or []),
        " ".join(insight.get("keywords") or []),
        " ".join(insight.get("situation_examples") or []),
        insight.get("best_quote", ""),
    ]).lower()

    score = 0.0
    for kw in user_keywords:
        if kw in combined:
            score += 2

    primary_stage = insight.get("primary_stage", "").lower()
    secondary = " ".join(insight.get("secondary_stages") or []).lower()
    for matched_stage in matched_stages:
        if matched_stage in primary_stage or matched_stage in secondary:
            score += 3

    relevance = insight.get("relevance_score") or 0
    score += relevance / 5

    return score


def find_relevant_insights(
    insights: list[dict],
    scenario: str,
    top_n: int = 5,
    expert_slug: Optional[str] = None,
) -> list[dict]:
    """Find the most relevant insights for a given scenario.

    If expert_slug is set, adjusts top_n based on data density:
    - <15 insights: return all with score > 0 (up to 8)
    - 15+: standard top_n with stage strength boost
    """
    user_keywords = [word.lower() for word in re.findall(r"\w+", scenario) if len(word) > 3]

    matched_stages = []
    scenario_lower = scenario.lower()
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(kw in scenario_lower for kw in keywords):
            matched_stages.append(stage)

    scored = []
    for insight in insights:
        score = score_insight(insight, user_keywords, matched_stages)
        if score > 0:
            scored.append((insight, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Adjust top_n for data-sparse experts (from persona plan)
    if expert_slug:
        total = len(insights)
        if total < 15:
            top_n = min(total, 8)
            return [i for i, s in scored if s > 0][:top_n]

    return [insight for insight, _ in scored[:top_n]]


def build_context(insights: list[dict]) -> str:
    """Build context string from relevant insights for the AI prompt."""
    parts = []
    for insight in insights:
        name = insight.get("influencer_name", "Unknown")
        stage = insight.get("primary_stage", "General")
        key = insight.get("key_insight", "")
        steps = insight.get("tactical_steps")
        situations = insight.get("situation_examples")
        quote = insight.get("best_quote", "")

        part = f"**{name}** ({stage}):\nInsight: {key}"
        if steps:
            if isinstance(steps, list):
                part += f"\nSteps: {', '.join(steps)}"
            else:
                part += f"\nSteps: {steps}"
        if situations:
            if isinstance(situations, list):
                part += f"\nWhen to use: {', '.join(situations)}"
            else:
                part += f"\nWhen to use: {situations}"
        if quote:
            part += f'\nKey quote: "{quote}"'

        # Add methodology context if tagged
        tags = insight.get("methodology_tags") or []
        if tags:
            method_strs = [f"{t['methodology_name']} > {t['name']}" for t in tags[:3]]
            part += f"\nMethodology: {', '.join(method_strs)}"

        parts.append(part)

    return "\n\n---\n\n".join(parts)
