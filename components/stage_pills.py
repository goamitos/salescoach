"""Stage filter pills and stage-related display components."""
from __future__ import annotations

from utils.data import STAGE_GROUPS, get_stage_color


def stage_badge_html(stage: str) -> str:
    """Render a single stage badge with color."""
    color_cls = get_stage_color(stage)
    return f'<span class="stage-badge {color_cls}">{stage}</span>'


def stage_group_options(counts: dict[str, int]) -> list[str]:
    """Build display options for the stage filter with counts.

    Returns list like: ["All stages (1893)", "Planning & Research (234)", ...]
    """
    options = [f"All stages ({counts.get('All', 0)})"]
    for group_name in STAGE_GROUPS:
        count = counts.get(group_name, 0)
        options.append(f"{group_name} ({count})")
    options.append(f"Mindset ({counts.get('Mindset', 0)})")
    return options


def stage_option_to_value(option: str) -> str:
    """Convert a display option back to internal value.

    'Planning & Research (234)' -> 'Planning & Research'
    'All stages (1893)' -> 'All'
    'Mindset (45)' -> 'General Sales Mindset'
    """
    if option.startswith("All stages"):
        return "All"
    if option.startswith("Mindset"):
        return "General Sales Mindset"
    # Strip the count suffix: 'Planning & Research (234)' -> 'Planning & Research'
    paren_idx = option.rfind(" (")
    if paren_idx > 0:
        return option[:paren_idx]
    return option


def value_to_stage_option(value: str, options: list[str]) -> str:
    """Find the display option for an internal value."""
    if value == "All":
        return options[0]
    if value == "General Sales Mindset":
        return options[-1]
    for opt in options:
        if opt.startswith(value):
            return opt
    return options[0]
