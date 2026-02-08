#!/usr/bin/env python3
"""
Seed sales methodologies and their components into the SQLite database.

Seeds 10 methodologies with ~50 components. Skeleton data includes IDs, names,
categories, keywords, and placeholder descriptions. Rich content (overview,
how_to_execute, example_scenario, etc.) is populated in Step 2 via
generate_methodology_content.py.

Usage:
    python seed_methodologies.py          # Seed skeleton data
    python seed_methodologies.py --stats  # Show current methodology counts

Idempotent: safe to run multiple times (INSERT OR REPLACE).
"""

import json
import logging
import sys
from pathlib import Path

from config import TMP_DIR
from db import get_connection, init_db, upsert_methodology, upsert_component, get_stats

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Methodology definitions
# ---------------------------------------------------------------------------
# Rich content fields (overview, how_to_execute, common_mistakes,
# example_scenario) are placeholder strings. They'll be replaced by
# Claude-generated content in Step 2.
# ---------------------------------------------------------------------------

METHODOLOGIES = [
    {
        "id": "meddic",
        "name": "MEDDIC",
        "author": "Jack Napoli & Dick Dunkel",
        "source": "Developed at PTC in the 1990s",
        "category": "qualification",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Needs Analysis", "Business Case Development"]),
    },
    {
        "id": "challenger",
        "name": "Challenger Sale",
        "author": "Matthew Dixon & Brent Adamson",
        "source": "The Challenger Sale (2011)",
        "category": "communication",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Demo & Presentation", "Business Case Development"]),
    },
    {
        "id": "spin",
        "name": "SPIN Selling",
        "author": "Neil Rackham",
        "source": "SPIN Selling (1988)",
        "category": "communication",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Needs Analysis"]),
    },
    {
        "id": "sandler",
        "name": "Sandler Selling System",
        "author": "David Sandler",
        "source": "Sandler Training (1967)",
        "category": "qualification",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Needs Analysis", "Procurement & Negotiation"]),
    },
    {
        "id": "gap",
        "name": "Gap Selling",
        "author": "Keenan",
        "source": "Gap Selling (2018)",
        "category": "problem-centric",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Needs Analysis", "Business Case Development"]),
    },
    {
        "id": "solution",
        "name": "Solution Selling",
        "author": "Michael Bosworth",
        "source": "Solution Selling (1995)",
        "category": "consultative",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Discovery", "Demo & Presentation", "Proof of Value"]),
    },
    {
        "id": "consultative",
        "name": "Consultative Selling",
        "author": "Mack Hanan",
        "source": "Consultative Selling (1970)",
        "category": "consultative",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Account Research", "Discovery", "Needs Analysis"]),
    },
    {
        "id": "bant",
        "name": "BANT",
        "author": "IBM",
        "source": "Developed at IBM in the 1960s",
        "category": "qualification",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Initial Contact", "Discovery"]),
    },
    {
        "id": "command_of_message",
        "name": "Command of the Message",
        "author": "Force Management",
        "source": "Force Management framework",
        "category": "value-messaging",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Demo & Presentation", "Business Case Development", "Procurement & Negotiation"]),
    },
    {
        "id": "value_selling",
        "name": "Value Selling",
        "author": "Value Selling Associates",
        "source": "Value Selling Framework",
        "category": "roi-driven",
        "overview": "",
        "core_philosophy": "",
        "when_to_use": "",
        "strengths": "",
        "limitations": "",
        "deal_stages": json.dumps(["Business Case Development", "Proof of Value", "Procurement & Negotiation"]),
    },
]


# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------
# Each component includes keywords for automatic insight tagging (Step 6).
# The keywords list should capture how sales experts naturally talk about
# the concept — not just the methodology's formal terminology.
# ---------------------------------------------------------------------------

COMPONENTS = [
    # --- MEDDIC ---
    {
        "id": "meddic_metrics",
        "methodology_id": "meddic",
        "name": "Metrics",
        "abbreviation": "M",
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["metrics", "quantifiable", "measurable outcome", "KPI", "ROI", "business impact", "success criteria", "benchmarks"],
    },
    {
        "id": "meddic_economic_buyer",
        "methodology_id": "meddic",
        "name": "Economic Buyer",
        "abbreviation": "E",
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["economic buyer", "budget holder", "decision maker", "purse strings", "final sign-off", "budget authority", "CFO", "VP", "C-suite"],
    },
    {
        "id": "meddic_decision_criteria",
        "methodology_id": "meddic",
        "name": "Decision Criteria",
        "abbreviation": "D",
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["decision criteria", "evaluation criteria", "requirements", "must-have", "scorecard", "selection criteria", "vendor comparison"],
    },
    {
        "id": "meddic_decision_process",
        "methodology_id": "meddic",
        "name": "Decision Process",
        "abbreviation": "D",
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["decision process", "buying process", "procurement", "approval chain", "committee", "stakeholder alignment", "timeline", "next steps"],
    },
    {
        "id": "meddic_identify_pain",
        "methodology_id": "meddic",
        "name": "Identify Pain",
        "abbreviation": "I",
        "sequence_order": 5,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["pain point", "identify pain", "business problem", "challenge", "frustration", "cost of inaction", "status quo", "burning platform"],
    },
    {
        "id": "meddic_champion",
        "methodology_id": "meddic",
        "name": "Champion",
        "abbreviation": "C",
        "sequence_order": 6,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["champion", "internal advocate", "coach", "mobilizer", "executive sponsor", "political ally", "insider", "sell internally"],
    },

    # --- Challenger Sale ---
    {
        "id": "challenger_teach",
        "methodology_id": "challenger",
        "name": "Teach",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["teach", "commercial insight", "reframe", "perspective", "educate", "thought leadership", "new way of thinking", "insight-led"],
    },
    {
        "id": "challenger_tailor",
        "methodology_id": "challenger",
        "name": "Tailor",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["tailor", "personalize", "stakeholder-specific", "resonate", "relevant", "custom message", "adapt", "audience"],
    },
    {
        "id": "challenger_take_control",
        "methodology_id": "challenger",
        "name": "Take Control",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["take control", "assertive", "push back", "constructive tension", "lead the conversation", "not afraid to disagree", "guide", "direct"],
    },

    # --- SPIN Selling ---
    {
        "id": "spin_situation",
        "methodology_id": "spin",
        "name": "Situation Questions",
        "abbreviation": "S",
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["situation questions", "current state", "background", "context", "how do you currently", "tell me about your process", "walk me through"],
    },
    {
        "id": "spin_problem",
        "methodology_id": "spin",
        "name": "Problem Questions",
        "abbreviation": "P",
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["problem questions", "difficulty", "dissatisfied", "struggle", "what challenges", "where does it break down", "limitations"],
    },
    {
        "id": "spin_implication",
        "methodology_id": "spin",
        "name": "Implication Questions",
        "abbreviation": "I",
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["implication", "consequence", "impact", "what happens if", "cost of", "effect on", "ripple effect", "downstream"],
    },
    {
        "id": "spin_need_payoff",
        "methodology_id": "spin",
        "name": "Need-Payoff Questions",
        "abbreviation": "N",
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["need-payoff", "benefit", "value", "how would it help", "what would it mean", "ideal solution", "imagine if", "worth"],
    },

    # --- Sandler Selling System ---
    {
        "id": "sandler_bonding_rapport",
        "methodology_id": "sandler",
        "name": "Bonding & Rapport",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["rapport", "bonding", "trust", "relationship", "personal connection", "likability", "comfortable", "authentic"],
    },
    {
        "id": "sandler_upfront_contract",
        "methodology_id": "sandler",
        "name": "Up-Front Contract",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["upfront contract", "agenda", "mutual agreement", "expectations", "ground rules", "what happens next", "commitment"],
    },
    {
        "id": "sandler_pain",
        "methodology_id": "sandler",
        "name": "Pain",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["pain funnel", "emotional pain", "surface pain", "business pain", "personal impact", "dig deeper", "why does that matter"],
    },
    {
        "id": "sandler_budget",
        "methodology_id": "sandler",
        "name": "Budget",
        "abbreviation": None,
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["budget", "investment", "money conversation", "financial commitment", "what have you set aside", "cost", "spend"],
    },
    {
        "id": "sandler_decision",
        "methodology_id": "sandler",
        "name": "Decision",
        "abbreviation": None,
        "sequence_order": 5,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["decision", "decision-making process", "who else is involved", "authority", "committee", "final say", "sign-off"],
    },
    {
        "id": "sandler_fulfillment",
        "methodology_id": "sandler",
        "name": "Fulfillment",
        "abbreviation": None,
        "sequence_order": 6,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["fulfillment", "solution presentation", "prescribe", "fit", "match solution to pain", "capabilities"],
    },
    {
        "id": "sandler_post_sell",
        "methodology_id": "sandler",
        "name": "Post-Sell",
        "abbreviation": None,
        "sequence_order": 7,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["post-sell", "buyer's remorse", "reinforce", "prevent regret", "next steps confirmation", "follow through"],
    },

    # --- Gap Selling ---
    {
        "id": "gap_current_state",
        "methodology_id": "gap",
        "name": "Current State",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["current state", "as-is", "today", "how things work now", "existing process", "status quo", "baseline"],
    },
    {
        "id": "gap_future_state",
        "methodology_id": "gap",
        "name": "Future State",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["future state", "desired outcome", "vision", "goal", "where do you want to be", "ideal", "to-be", "aspiration"],
    },
    {
        "id": "gap_the_gap",
        "methodology_id": "gap",
        "name": "The Gap",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["gap", "delta", "distance", "what's missing", "bridge", "difference between", "cost of the gap", "unrealized potential"],
    },

    # --- Solution Selling ---
    {
        "id": "solution_diagnose",
        "methodology_id": "solution",
        "name": "Diagnose",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["diagnose", "discovery", "understand the problem", "root cause", "assessment", "audit", "investigate"],
    },
    {
        "id": "solution_design",
        "methodology_id": "solution",
        "name": "Design",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["design solution", "architect", "tailored solution", "custom approach", "proposal", "solution map", "blueprint"],
    },
    {
        "id": "solution_deliver",
        "methodology_id": "solution",
        "name": "Deliver",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["deliver", "implement", "prove value", "pilot", "POC", "demonstrate results", "onboard", "launch"],
    },

    # --- Consultative Selling ---
    {
        "id": "consultative_research",
        "methodology_id": "consultative",
        "name": "Research",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["research", "preparation", "homework", "industry knowledge", "account intelligence", "pre-call planning", "know your buyer"],
    },
    {
        "id": "consultative_ask",
        "methodology_id": "consultative",
        "name": "Ask",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["ask questions", "open-ended", "curious", "probe", "explore", "dig deeper", "understand needs"],
    },
    {
        "id": "consultative_listen",
        "methodology_id": "consultative",
        "name": "Listen",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["listen", "active listening", "hear", "understand", "empathy", "reflect back", "paraphrase", "validate"],
    },
    {
        "id": "consultative_advise",
        "methodology_id": "consultative",
        "name": "Advise",
        "abbreviation": None,
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["advise", "recommend", "trusted advisor", "guidance", "expertise", "prescribe", "counsel", "add value"],
    },

    # --- BANT ---
    {
        "id": "bant_budget",
        "methodology_id": "bant",
        "name": "Budget",
        "abbreviation": "B",
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["budget", "funding", "allocated", "spend", "investment", "price range", "financial resources", "can they afford"],
    },
    {
        "id": "bant_authority",
        "methodology_id": "bant",
        "name": "Authority",
        "abbreviation": "A",
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["authority", "decision maker", "who decides", "sign off", "approval", "influencer", "gatekeeper", "power"],
    },
    {
        "id": "bant_need",
        "methodology_id": "bant",
        "name": "Need",
        "abbreviation": "N",
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["need", "requirement", "must have", "priority", "urgency", "business need", "problem to solve", "pain"],
    },
    {
        "id": "bant_timeline",
        "methodology_id": "bant",
        "name": "Timeline",
        "abbreviation": "T",
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["timeline", "urgency", "when", "deadline", "time frame", "implementation date", "go-live", "fiscal year"],
    },

    # --- Command of the Message ---
    {
        "id": "cotm_required_capabilities",
        "methodology_id": "command_of_message",
        "name": "Required Capabilities",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["required capabilities", "must-have features", "differentiators", "unique value", "what we do that others can't", "competitive advantage"],
    },
    {
        "id": "cotm_positive_business_outcomes",
        "methodology_id": "command_of_message",
        "name": "Positive Business Outcomes",
        "abbreviation": "PBO",
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["positive business outcomes", "business results", "revenue impact", "cost savings", "efficiency gains", "strategic value", "outcomes"],
    },
    {
        "id": "cotm_metrics",
        "methodology_id": "command_of_message",
        "name": "Metrics",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["metrics", "proof points", "case study", "data", "numbers", "quantify", "evidence", "benchmark"],
    },
    {
        "id": "cotm_before_after",
        "methodology_id": "command_of_message",
        "name": "Before/After Scenarios",
        "abbreviation": None,
        "sequence_order": 4,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["before and after", "transformation", "day in the life", "with vs without", "contrast", "improvement story"],
    },

    # --- Value Selling ---
    {
        "id": "value_discover",
        "methodology_id": "value_selling",
        "name": "Discover Value",
        "abbreviation": None,
        "sequence_order": 1,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["discover value", "uncover", "what matters most", "business drivers", "value drivers", "priorities", "strategic goals"],
    },
    {
        "id": "value_create",
        "methodology_id": "value_selling",
        "name": "Create Value",
        "abbreviation": None,
        "sequence_order": 2,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["create value", "build business case", "ROI", "total cost of ownership", "TCO", "value proposition", "justify investment"],
    },
    {
        "id": "value_capture",
        "methodology_id": "value_selling",
        "name": "Capture Value",
        "abbreviation": None,
        "sequence_order": 3,
        "description": "",
        "how_to_execute": "",
        "common_mistakes": "",
        "example_scenario": "",
        "keywords": ["capture value", "negotiate", "defend price", "value-based pricing", "close on value", "avoid discounting", "premium"],
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_methodologies() -> None:
    """Seed all methodologies and components into the database."""
    init_db()
    conn = get_connection()

    try:
        for m in METHODOLOGIES:
            upsert_methodology(conn, m)
        logger.info("Seeded %d methodologies", len(METHODOLOGIES))

        for c in COMPONENTS:
            upsert_component(conn, c)
        logger.info("Seeded %d components", len(COMPONENTS))

        conn.commit()

        stats = get_stats(conn)
        print("=" * 50)
        print("METHODOLOGY SEED COMPLETE")
        print("=" * 50)
        print(f"  Methodologies: {stats['methodologies']}")
        print(f"  Components:    {stats['methodology_components']}")
        print("=" * 50)
    finally:
        conn.close()


def load_generated_content() -> None:
    """Load Claude-generated content from .tmp/methodologies/ into the DB.

    Reads each JSON file, merges generated rich content with existing
    skeleton records (preserving keywords from skeleton data).
    """
    generated_dir = TMP_DIR / "methodologies"
    json_files = sorted(generated_dir.glob("*.json"))

    if not json_files:
        logger.error("No generated files found in %s", generated_dir)
        return

    init_db()
    conn = get_connection()

    try:
        loaded = 0
        components_loaded = 0

        for f in json_files:
            with open(f) as fh:
                data = json.load(fh)

            mid = data["id"]

            # Update methodology-level content
            upsert_methodology(conn, {
                "id": mid,
                "name": data["name"],
                "author": data.get("author", ""),
                "source": data.get("source", ""),
                "category": data.get("category", ""),
                "overview": data.get("overview", ""),
                "core_philosophy": data.get("core_philosophy", ""),
                "when_to_use": data.get("when_to_use", ""),
                "strengths": data.get("strengths", ""),
                "limitations": data.get("limitations", ""),
                "deal_stages": json.dumps(data.get("deal_stages", [])),
            })
            loaded += 1

            # Update component-level content
            for comp in data.get("components", []):
                upsert_component(conn, {
                    "id": comp["id"],
                    "methodology_id": mid,
                    "name": comp["name"],
                    "abbreviation": comp.get("abbreviation"),
                    "sequence_order": comp.get("sequence_order"),
                    "description": comp.get("description", ""),
                    "how_to_execute": comp.get("how_to_execute", ""),
                    "common_mistakes": comp.get("common_mistakes", ""),
                    "example_scenario": comp.get("example_scenario", ""),
                    "keywords": comp.get("keywords", []),
                })
                components_loaded += 1

            logger.info("Loaded %s (%d components)", data["name"], len(data.get("components", [])))

        conn.commit()

        stats = get_stats(conn)
        print("=" * 50)
        print("GENERATED CONTENT LOADED")
        print("=" * 50)
        print(f"  Methodologies updated: {loaded}")
        print(f"  Components updated:    {components_loaded}")
        print(f"  DB totals: {stats['methodologies']} methodologies, {stats['methodology_components']} components")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == "__main__":
    if "--stats" in sys.argv:
        init_db()
        conn = get_connection()
        try:
            stats = get_stats(conn)
            print(f"Methodologies: {stats['methodologies']}")
            print(f"Components: {stats['methodology_components']}")
        finally:
            conn.close()
    elif "--from-generated" in sys.argv:
        load_generated_content()
    else:
        seed_methodologies()
