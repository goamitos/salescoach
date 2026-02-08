"""Methodology display components: cards, badges, explorer."""
from __future__ import annotations

from utils.data import get_methodology_color


def methodology_card_html(methodology: dict) -> str:
    """Render a methodology card for the explorer.

    Shows name, author, core philosophy, and component pills.
    """
    name = methodology.get("name", "")
    author = methodology.get("author", "")
    source = methodology.get("source", "")
    category = methodology.get("category", "qualification")
    philosophy = methodology.get("core_philosophy", "")
    components = methodology.get("components", [])
    color_cls = get_methodology_color(category)

    author_html = ""
    if author:
        source_text = f" ({source})" if source else ""
        author_html = f'<p class="author">{author}{source_text}</p>'

    philosophy_html = ""
    if philosophy:
        philosophy_html = f'<p class="philosophy">{philosophy}</p>'

    component_pills = ""
    if components:
        pills = "".join(
            f'<span class="component-pill">{c.get("abbreviation") or c.get("name", "")}</span>'
            for c in components
        )
        component_pills = f'<div class="component-list">{pills}</div>'

    return f"""<div class="methodology-card">
    <span class="methodology-badge {color_cls}" style="margin-bottom:8px">{category.title()}</span>
    <p class="title">{name}</p>
    {author_html}
    {philosophy_html}
    {component_pills}
</div>"""


def methodology_component_detail_html(component: dict, methodology_name: str) -> str:
    """Render a detailed view of a methodology component.

    Shows description, how-to-execute, common mistakes, and example scenario.
    """
    name = component.get("name", "")
    abbrev = component.get("abbreviation", "")
    description = component.get("description", "")
    how_to = component.get("how_to_execute", "")
    mistakes = component.get("common_mistakes", "")
    example = component.get("example_scenario", "")

    title = f"{abbrev} - {name}" if abbrev else name

    sections = []
    if description:
        sections.append(f'<p style="font-size:0.9rem;color:var(--text-primary);line-height:1.5;margin-bottom:12px">{description}</p>')

    if how_to:
        sections.append(f"""<div style="margin-bottom:12px">
    <p style="font-size:0.75rem;color:var(--gold-light);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">How to Execute</p>
    <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.5">{how_to}</p>
</div>""")

    if mistakes:
        sections.append(f"""<div style="margin-bottom:12px">
    <p style="font-size:0.75rem;color:var(--stage-close);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Common Mistakes</p>
    <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.5">{mistakes}</p>
</div>""")

    if example:
        sections.append(f"""<div style="margin-bottom:12px;padding:12px;background:var(--bg-elevated);border-radius:var(--radius-md);border-left:2px solid var(--gold-dim)">
    <p style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Example Scenario</p>
    <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.5;font-style:italic">{example}</p>
</div>""")

    return f"""<div>
    <h4 style="font-family:'Playfair Display',serif;margin:0 0 8px;color:var(--text-primary)">{title}</h4>
    <p style="font-size:0.75rem;color:var(--text-muted);margin-bottom:12px">{methodology_name}</p>
    {"".join(sections)}
</div>"""
