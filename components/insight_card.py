"""Reusable insight card HTML component.

Used on the Insights page and as source cards in chat responses.
"""
from __future__ import annotations

from utils.data import get_avatar_base64, get_methodology_color, get_stage_color


def insight_card_html(insight: dict, show_expert: bool = True) -> str:
    """Render a full insight card as HTML.

    Shows expert avatar, key insight, tactical steps, best quote,
    stage badge, and methodology tags.
    """
    slug = insight.get("influencer_slug", "")
    name = insight.get("influencer_name", "Unknown")
    stage = insight.get("primary_stage", "General")
    key_insight = insight.get("key_insight", "")
    tactical_steps = insight.get("tactical_steps") or []
    quote = insight.get("best_quote", "")
    source_url = insight.get("source_url", "")
    methodology_tags = insight.get("methodology_tags") or []

    # Expert header
    header_html = ""
    if show_expert:
        avatar_b64 = get_avatar_base64(slug)
        avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""
        stage_color = get_stage_color(stage)
        header_html = f"""<div class="card-header">
    <img src="{avatar_src}" alt="{name}">
    <span class="expert-name">{name}</span>
    <span class="stage-badge {stage_color}">{stage}</span>
</div>"""

    # Key insight
    insight_html = f'<p class="key-insight">{key_insight}</p>' if key_insight else ""

    # Tactical steps
    steps_html = ""
    if tactical_steps:
        if isinstance(tactical_steps, list):
            steps_text = "<br>".join(f"&bull; {s}" for s in tactical_steps[:4])
        else:
            steps_text = str(tactical_steps)
        steps_html = f'<div class="tactical-steps">{steps_text}</div>'

    # Quote
    quote_html = f'<div class="quote">"{quote}"</div>' if quote else ""

    # Tags row: methodology + source
    tags_html = ""
    tag_items = []
    for tag in methodology_tags[:3]:
        cat = tag.get("category", "qualification")
        color_cls = get_methodology_color(cat)
        tag_items.append(
            f'<span class="methodology-badge {color_cls}">{tag.get("methodology_name", "")} &rsaquo; {tag.get("name", "")}</span>'
        )
    if source_url:
        tag_items.append(
            f'<a href="{source_url}" target="_blank" style="font-size:0.7rem;color:var(--gold-dim);text-decoration:none;font-family:Inter,sans-serif">View source &rarr;</a>'
        )
    if tag_items:
        tags_html = f'<div class="tags">{"".join(tag_items)}</div>'

    return f"""<div class="insight-card">
    {header_html}
    {insight_html}
    {steps_html}
    {quote_html}
    {tags_html}
</div>"""


def source_card_html(insight: dict) -> str:
    """Render a compact source card for inline chat display.

    Shows avatar, expert name, stage, and a truncated quote.
    """
    slug = insight.get("influencer_slug", "")
    name = insight.get("influencer_name", "Unknown")
    stage = insight.get("primary_stage", "General")
    quote = insight.get("best_quote", "")
    source_url = insight.get("source_url", "")

    avatar_b64 = get_avatar_base64(slug)
    avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

    quote_html = ""
    if quote:
        short_quote = quote[:80] + "..." if len(quote) > 80 else quote
        quote_html = f'<div class="source-quote">"{short_quote}"</div>'

    link_attr = f' onclick="window.open(\'{source_url}\', \'_blank\')" style="cursor:pointer"' if source_url else ""

    return f"""<div class="source-card"{link_attr}>
    <img src="{avatar_src}" alt="{name}">
    <div class="source-info">
        <div class="source-name">{name}</div>
        <div class="source-stage">{stage}</div>
        {quote_html}
    </div>
</div>"""


def methodology_tag_html(tag: dict) -> str:
    """Render a single methodology tag badge."""
    cat = tag.get("category", "qualification")
    color_cls = get_methodology_color(cat)
    method_name = tag.get("methodology_name", "")
    comp_name = tag.get("name", "")
    return f'<span class="methodology-badge {color_cls}">{method_name} &rsaquo; {comp_name}</span>'
