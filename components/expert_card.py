"""Reusable expert card HTML component.

Used on the Experts page grid and in @st.dialog profile modals.
"""
from __future__ import annotations

from typing import Optional

from utils.data import (
    format_followers,
    get_avatar_base64,
    get_confidence_label,
    get_insight_counts_by_expert,
    get_persona,
    load_insights,
)


def expert_card_html(
    slug: str,
    name: str,
    specialty: str,
    followers: Optional[int] = None,
    insight_count: Optional[int] = None,
) -> str:
    """Render an expert card as HTML.

    Shows avatar, name, specialty, confidence badge, framework tags,
    and insight/follower counts.
    """
    avatar_b64 = get_avatar_base64(slug)
    avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

    # Persona data for confidence badge and frameworks
    persona = get_persona(slug)
    confidence_html = ""
    frameworks_html = ""

    if persona:
        confidence = persona.get("confidence", "medium")
        label = get_confidence_label(confidence)
        confidence_html = f'<span class="confidence-badge {confidence}">{label}</span>'

        frameworks = persona.get("signature_frameworks", [])[:3]
        if frameworks:
            tags = "".join(
                f'<span class="framework-tag">{fw["name"]}</span>'
                for fw in frameworks
            )
            frameworks_html = f'<div style="margin-top: 8px">{tags}</div>'

    # Counts
    followers_str = format_followers(followers) if followers else ""
    meta_parts = []
    if insight_count is not None:
        meta_parts.append(f'<span class="count">{insight_count}</span> insights')
    if followers_str:
        meta_parts.append(f'{followers_str} followers')
    meta_html = " &middot; ".join(meta_parts)

    return f"""<div class="expert-card">
    <img src="{avatar_src}" class="avatar" alt="{name}">
    <p class="name">{name}</p>
    {confidence_html}
    <p class="specialty">{specialty}</p>
    <div class="meta">{meta_html}</div>
    {frameworks_html}
</div>"""


def expert_profile_html(
    slug: str,
    name: str,
    specialty: str,
    followers: Optional[int] = None,
    focus_areas: Optional[list[str]] = None,
) -> str:
    """Render a full expert profile for the @st.dialog modal.

    Shows expanded avatar, bio, frameworks, stage strengths, and links.
    """
    avatar_b64 = get_avatar_base64(slug)
    avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

    persona = get_persona(slug)
    followers_str = format_followers(followers)

    # Insight count
    counts = get_insight_counts_by_expert(load_insights())
    insight_count = counts.get(slug, 0)

    # Confidence badge
    confidence_html = ""
    if persona:
        confidence = persona.get("confidence", "medium")
        label = get_confidence_label(confidence)
        confidence_html = f'<span class="confidence-badge {confidence}">{label}</span>'

    # Voice description
    voice_html = ""
    if persona and persona.get("voice_profile"):
        voice = persona["voice_profile"]
        style = voice.get("communication_style", "")
        if style:
            voice_html = f'<p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.5;margin:8px 0">{style}</p>'

    # Frameworks
    frameworks_html = ""
    if persona and persona.get("signature_frameworks"):
        fw_items = ""
        for fw in persona["signature_frameworks"][:5]:
            desc = fw.get("description", "")
            fw_items += f'<div style="margin-bottom:8px"><strong style="color:var(--gold-light);font-size:0.85rem">{fw["name"]}</strong><br><span style="font-size:0.8rem;color:var(--text-secondary)">{desc}</span></div>'
        frameworks_html = f'<div style="margin-top:12px"><p style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Signature Frameworks</p>{fw_items}</div>'

    # Focus areas
    focus_html = ""
    if focus_areas:
        pills = "".join(
            f'<span class="framework-tag">{area}</span>' for area in focus_areas
        )
        focus_html = f'<div style="margin-top:8px">{pills}</div>'

    # Stage strengths
    strengths_html = ""
    if persona and persona.get("deal_stage_strengths"):
        from utils.data import get_stage_color
        badges = "".join(
            f'<span class="stage-badge {get_stage_color(s)}">{s}</span> '
            for s in persona["deal_stage_strengths"][:4]
        )
        strengths_html = f'<div style="margin-top:8px"><p style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Stage Strengths</p>{badges}</div>'

    return f"""<div style="text-align:center;margin-bottom:16px">
    <img src="{avatar_src}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid var(--gold-dim);margin-bottom:8px">
    <h3 style="margin:0;font-size:1.2rem">{name}</h3>
    {confidence_html}
    <p style="font-size:0.85rem;color:var(--text-secondary);font-style:italic;margin:4px 0">{specialty}</p>
    <p style="font-size:0.8rem;color:var(--text-muted)">{insight_count} insights{' &middot; ' + followers_str + ' followers' if followers_str else ''}</p>
</div>
{voice_html}
{focus_html}
{frameworks_html}
{strengths_html}"""
