"""Data loading, caching, and filtering.

Reads from SQLite (primary) with Airtable fallback. Loads personas and
methodology data. All functions use Streamlit caching where appropriate.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "sales_coach.db"
PERSONAS_PATH = PROJECT_ROOT / "data" / "personas.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "influencers.json"

# Deal stage groups for sidebar/filter navigation
STAGE_GROUPS = {
    "Planning & Research": [
        "Territory Planning",
        "Account Research",
        "Stakeholder Mapping",
    ],
    "Outreach & Contact": [
        "Outreach Strategy",
        "Initial Contact",
    ],
    "Discovery & Analysis": [
        "Discovery",
        "Needs Analysis",
    ],
    "Present & Prove Value": [
        "Demo & Presentation",
        "Business Case Development",
        "Proof of Value",
    ],
    "Close & Grow": [
        "RFP/RFQ Response",
        "Procurement & Negotiation",
        "Closing",
        "Onboarding & Expansion",
    ],
}

# Map stage names to their CSS color class
STAGE_COLOR_MAP = {
    "Territory Planning": "planning",
    "Account Research": "planning",
    "Stakeholder Mapping": "planning",
    "Outreach Strategy": "outreach",
    "Initial Contact": "outreach",
    "Discovery": "discovery",
    "Needs Analysis": "discovery",
    "Demo & Presentation": "present",
    "Business Case Development": "present",
    "Proof of Value": "present",
    "RFP/RFQ Response": "close",
    "Procurement & Negotiation": "close",
    "Closing": "close",
    "Onboarding & Expansion": "close",
    "General Sales Mindset": "mindset",
}

# Map methodology categories to CSS class
METHODOLOGY_CATEGORY_MAP = {
    "qualification": "qualification",
    "communication": "communication",
    "negotiation": "negotiation",
    "consultative": "consultative",
    "value": "value",
}


def get_stage_color(stage: str) -> str:
    """Get the CSS color class for a stage name."""
    return STAGE_COLOR_MAP.get(stage, "mindset")


def get_methodology_color(category: str) -> str:
    """Get the CSS color class for a methodology category."""
    return METHODOLOGY_CATEGORY_MAP.get(category, "qualification")


# ── SQLite connection ──────────────────────────────────

def _get_db_connection() -> Optional[sqlite3.Connection]:
    """Get a read-only SQLite connection if DB exists."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ── Influencer / Expert loading ────────────────────────

@st.cache_data(ttl=600)
def load_influencers() -> list[dict]:
    """Load active influencers from the registry JSON."""
    try:
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, "r") as f:
                data = json.load(f)

            influencers = []
            for inf in data.get("influencers", []):
                if inf.get("status") == "active":
                    linkedin = inf.get("platforms", {}).get("linkedin", {})
                    followers = linkedin.get("followers")
                    metadata = inf.get("metadata", {})
                    specialty = metadata.get("notes", "")
                    focus_areas = metadata.get("focus_areas", [])

                    influencers.append({
                        "name": inf["name"],
                        "slug": inf["slug"],
                        "specialty": specialty,
                        "followers": followers,
                        "focus_areas": focus_areas,
                    })

            if influencers:
                return influencers
    except Exception:
        pass
    return []


def get_influencer_name(slug: str) -> str:
    """Get influencer name from slug."""
    if slug == "collective-wisdom":
        return "Collective Wisdom"
    for inf in load_influencers():
        if inf["slug"] == slug:
            return inf["name"]
    return slug


def get_influencer_details(slug: str) -> dict:
    """Get full influencer details from slug."""
    influencers = load_influencers()
    if slug == "collective-wisdom":
        return {
            "name": "Collective Wisdom",
            "slug": "collective-wisdom",
            "specialty": f"Combined insights from all {len(influencers)} experts",
            "followers": None,
            "focus_areas": [],
        }
    for inf in influencers:
        if inf["slug"] == slug:
            return inf
    return {"name": slug, "slug": slug, "specialty": "", "followers": None, "focus_areas": []}


def format_followers(count: Optional[int]) -> str:
    """Format follower count for display."""
    if count is None:
        return ""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


# ── Persona loading ────────────────────────────────────

@st.cache_data(ttl=600)
def load_personas() -> dict[str, dict]:
    """Load persona profiles keyed by slug.

    Returns empty dict if personas.json doesn't exist yet
    (ai-personas workstream hasn't run).
    """
    try:
        if PERSONAS_PATH.exists():
            with open(PERSONAS_PATH, "r") as f:
                personas_list = json.load(f)
            return {p["slug"]: p for p in personas_list}
    except Exception:
        pass
    return {}


def get_persona(slug: str) -> Optional[dict]:
    """Get a single persona profile by expert slug."""
    return load_personas().get(slug)


def get_confidence_label(confidence: str) -> str:
    """Map confidence level to display label."""
    labels = {
        "high": "Deep Profile",
        "medium": "Standard",
        "low": "Limited",
    }
    return labels.get(confidence, "Standard")


# ── Insight loading (SQLite primary, Airtable fallback) ─

@st.cache_data(ttl=300)
def load_insights() -> list[dict]:
    """Load all insights. Tries SQLite first, falls back to Airtable."""
    conn = _get_db_connection()
    if conn:
        return _load_insights_sqlite(conn)
    return _load_insights_airtable()


def _load_insights_sqlite(conn: sqlite3.Connection) -> list[dict]:
    """Load insights from SQLite database."""
    try:
        rows = conn.execute(
            "SELECT * FROM insights ORDER BY relevance_score DESC"
        ).fetchall()

        insights = []
        for row in rows:
            insight = dict(row)
            # Parse JSON array fields
            for field in ("secondary_stages", "tactical_steps", "keywords",
                          "situation_examples"):
                val = insight.get(field)
                if val and isinstance(val, str):
                    try:
                        insight[field] = json.loads(val)
                    except json.JSONDecodeError:
                        insight[field] = []

            # Load methodology tags for this insight
            tags = conn.execute(
                """SELECT imt.component_id, imt.confidence, mc.name, mc.methodology_id, m.name as methodology_name, m.category
                   FROM insight_methodology_tags imt
                   JOIN methodology_components mc ON imt.component_id = mc.id
                   JOIN methodologies m ON mc.methodology_id = m.id
                   WHERE imt.insight_id = ?
                   ORDER BY imt.confidence DESC""",
                (insight["id"],),
            ).fetchall()
            insight["methodology_tags"] = [dict(t) for t in tags]
            insights.append(insight)

        conn.close()
        return insights
    except Exception:
        conn.close()
        return []


def _load_insights_airtable() -> list[dict]:
    """Fallback: load insights from Airtable, normalizing to SQLite schema."""
    try:
        secrets = _get_airtable_secrets()
        if not all(secrets.values()):
            return []

        from pyairtable import Api
        api = Api(secrets["airtable_key"])
        table = api.table(secrets["airtable_base"].split("/")[0], secrets["airtable_table"])
        raw_records = table.all()

        insights = []
        for record in raw_records:
            fields = record.get("fields", {})
            slug = _name_to_slug(fields.get("Influencer", "unknown"))
            insights.append({
                "id": record.get("id", ""),
                "influencer_slug": slug,
                "influencer_name": fields.get("Influencer", "Unknown"),
                "source_type": (fields.get("Source Type") or "").lower(),
                "source_url": fields.get("Source URL", ""),
                "date_collected": fields.get("Date Collected", ""),
                "primary_stage": fields.get("Primary Stage", "General"),
                "secondary_stages": _parse_csv(fields.get("Secondary Stages", "")),
                "key_insight": fields.get("Key Insight", ""),
                "tactical_steps": _parse_csv(fields.get("Tactical Steps", "")),
                "keywords": _parse_csv(fields.get("Keywords", "")),
                "situation_examples": _parse_csv(fields.get("Situation Examples", "")),
                "best_quote": fields.get("Best Quote", ""),
                "relevance_score": fields.get("Relevance Score", 0),
                "methodology_tags": [],
            })
        return insights
    except Exception:
        return []


def _get_airtable_secrets() -> dict:
    """Get Airtable secrets from Streamlit secrets or env."""
    try:
        return {
            "airtable_key": st.secrets["AIRTABLE_API_KEY"],
            "airtable_base": st.secrets["AIRTABLE_BASE_ID"],
            "airtable_table": st.secrets.get("AIRTABLE_TABLE_NAME", "Sales Wisdom"),
        }
    except Exception:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return {
            "airtable_key": os.getenv("AIRTABLE_API_KEY"),
            "airtable_base": os.getenv("AIRTABLE_BASE_ID"),
            "airtable_table": os.getenv("AIRTABLE_TABLE_NAME", "Sales Wisdom"),
        }


def _name_to_slug(name: str) -> str:
    """Convert 'Chris Voss' to 'chris-voss'."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _parse_csv(value: str) -> list[str]:
    """Parse a comma-separated string into a list."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


# ── Insight filtering ──────────────────────────────────

def filter_insights(
    insights: list[dict],
    expert_slug: Optional[str] = None,
    stage_group: Optional[str] = None,
    methodology_id: Optional[str] = None,
    search_query: Optional[str] = None,
) -> list[dict]:
    """Filter insights by expert, stage group, methodology, or search text."""
    filtered = insights

    # Filter by expert
    if expert_slug and expert_slug != "collective-wisdom":
        expert_name = get_influencer_name(expert_slug)
        filtered = [
            i for i in filtered
            if i.get("influencer_name", "").lower() == expert_name.lower()
            or i.get("influencer_slug", "") == expert_slug
        ]

    # Filter by stage group
    if stage_group and stage_group != "All":
        if stage_group == "General Sales Mindset":
            stages = ["General Sales Mindset"]
        else:
            stages = STAGE_GROUPS.get(stage_group, [])
        if stages:
            stages_lower = [s.lower() for s in stages]
            filtered = [
                i for i in filtered
                if i.get("primary_stage", "").lower() in stages_lower
                or any(
                    s.lower() in stages_lower
                    for s in (i.get("secondary_stages") or [])
                )
            ]

    # Filter by methodology
    if methodology_id:
        filtered = [
            i for i in filtered
            if any(
                t.get("methodology_id") == methodology_id
                for t in (i.get("methodology_tags") or [])
            )
        ]

    # Text search (simple keyword matching — FTS5 used in SQLite path)
    if search_query:
        query_lower = search_query.lower()
        keywords = [w for w in query_lower.split() if len(w) > 2]
        filtered = [
            i for i in filtered
            if any(
                kw in (i.get("key_insight", "") + " " +
                       i.get("best_quote", "") + " " +
                       " ".join(i.get("keywords") or []) + " " +
                       " ".join(i.get("tactical_steps") or [])).lower()
                for kw in keywords
            )
        ]

    return filtered


def get_insight_counts_by_expert(insights: list[dict]) -> dict[str, int]:
    """Count insights per expert slug."""
    counts: dict[str, int] = {}
    for i in insights:
        slug = i.get("influencer_slug", "unknown")
        counts[slug] = counts.get(slug, 0) + 1
    return counts


def get_stage_counts(insights: list[dict]) -> dict[str, int]:
    """Count insights per stage group."""
    counts = {"All": len(insights)}
    for group_name, stages in STAGE_GROUPS.items():
        stages_lower = [s.lower() for s in stages]
        count = sum(
            1 for i in insights
            if i.get("primary_stage", "").lower() in stages_lower
        )
        counts[group_name] = count
    mindset_count = sum(
        1 for i in insights
        if i.get("primary_stage", "").lower() == "general sales mindset"
    )
    counts["Mindset"] = mindset_count
    return counts


# ── Methodology loading ────────────────────────────────

@st.cache_data(ttl=600)
def load_methodologies() -> list[dict]:
    """Load all methodologies with their components from SQLite.

    Returns empty list if DB doesn't exist yet.
    """
    conn = _get_db_connection()
    if not conn:
        return []
    try:
        rows = conn.execute("SELECT * FROM methodologies ORDER BY name").fetchall()
        methodologies = []
        for row in rows:
            m = dict(row)
            # Parse JSON fields
            if m.get("deal_stages") and isinstance(m["deal_stages"], str):
                try:
                    m["deal_stages"] = json.loads(m["deal_stages"])
                except json.JSONDecodeError:
                    m["deal_stages"] = []

            # Load components
            components = conn.execute(
                """SELECT * FROM methodology_components
                   WHERE methodology_id = ?
                   ORDER BY sequence_order""",
                (m["id"],),
            ).fetchall()
            m["components"] = [dict(c) for c in components]
            # Parse component keyword JSON
            for c in m["components"]:
                if c.get("keywords") and isinstance(c["keywords"], str):
                    try:
                        c["keywords"] = json.loads(c["keywords"])
                    except json.JSONDecodeError:
                        c["keywords"] = []
            methodologies.append(m)
        conn.close()
        return methodologies
    except Exception:
        conn.close()
        return []


def get_methodology(methodology_id: str) -> Optional[dict]:
    """Get a single methodology by ID."""
    for m in load_methodologies():
        if m["id"] == methodology_id:
            return m
    return None


# ── FTS5 search (when SQLite available) ────────────────

def search_insights_fts(query: str, limit: int = 20) -> list[dict]:
    """Full-text search using FTS5. Falls back to in-memory filter."""
    conn = _get_db_connection()
    if not conn:
        return filter_insights(load_insights(), search_query=query)[:limit]

    try:
        rows = conn.execute(
            """SELECT i.*, rank
               FROM insights_fts fts
               JOIN insights i ON fts.id = i.id
               WHERE insights_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
        conn.close()
        results = []
        for row in rows:
            insight = dict(row)
            for field in ("secondary_stages", "tactical_steps", "keywords",
                          "situation_examples"):
                val = insight.get(field)
                if val and isinstance(val, str):
                    try:
                        insight[field] = json.loads(val)
                    except json.JSONDecodeError:
                        insight[field] = []
            insight["methodology_tags"] = []
            results.append(insight)
        return results
    except Exception:
        conn.close()
        return filter_insights(load_insights(), search_query=query)[:limit]


# ── Leadership Hub helpers ────────────────────────────

@st.cache_data(ttl=300)
def load_leader_insights() -> list[dict]:
    """Load insights tagged for VP Sales / CRO audience."""
    conn = _get_db_connection()
    if not conn:
        return []
    try:
        rows = conn.execute("""
            SELECT * FROM insights
            WHERE (target_audience LIKE '%"vp_sales"%' OR target_audience LIKE '%"cro"%')
              AND audience_confidence >= 0.7
            ORDER BY relevance_score DESC
        """).fetchall()
        insights = []
        for row in rows:
            insight = dict(row)
            for field in ("secondary_stages", "tactical_steps", "keywords",
                          "situation_examples", "target_audience"):
                val = insight.get(field)
                if val and isinstance(val, str):
                    try:
                        insight[field] = json.loads(val)
                    except json.JSONDecodeError:
                        insight[field] = []
            insights.append(insight)
        conn.close()
        return insights
    except Exception:
        conn.close()
        return []


def get_leader_stats(insights: list[dict]) -> dict:
    """Compute aggregate stats for the Leadership Hub dashboard."""
    if not insights:
        return {"total": 0, "by_stage": {}, "by_influencer": {}, "top_keywords": []}

    by_stage: dict[str, int] = {}
    by_influencer: dict[str, int] = {}
    keyword_counts: dict[str, int] = {}

    for i in insights:
        stage = i.get("primary_stage", "General")
        by_stage[stage] = by_stage.get(stage, 0) + 1

        name = i.get("influencer_name", "Unknown")
        by_influencer[name] = by_influencer.get(name, 0) + 1

        for kw in (i.get("keywords") or []):
            if isinstance(kw, str):
                keyword_counts[kw.lower()] = keyword_counts.get(kw.lower(), 0) + 1

    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "total": len(insights),
        "by_stage": dict(sorted(by_stage.items(), key=lambda x: x[1], reverse=True)),
        "by_influencer": dict(sorted(by_influencer.items(), key=lambda x: x[1], reverse=True)[:15]),
        "top_keywords": top_keywords,
    }


# ── Avatar helpers ─────────────────────────────────────

@st.cache_data(ttl=3600)
def get_avatar_base64(slug: str) -> str:
    """Get base64-encoded avatar for an expert. Cached aggressively."""
    import base64
    avatar_path = PROJECT_ROOT / "assets" / "avatars" / f"{slug}.png"
    if avatar_path.exists():
        with open(avatar_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""
