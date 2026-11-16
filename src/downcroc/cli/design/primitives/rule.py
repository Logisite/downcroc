"""Rule primitives: hairlines and dividers."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def hairline(theme: Theme, *, width: int = 40) -> Text:
    """A dim horizontal hairline."""
    width = max(width, theme.space_4)
    return Text("─" * width, style=theme.style("border_hairline"))


def divider(theme: Theme, *, width: int = 40, label: str = "") -> Text:
    """A labeled divider: ── label ──."""
    width = max(width, theme.space_4)
    if not label:
        return hairline(theme, width=width)
    text = f" {label} "
    side = max(theme.space_2, (width - len(text)) // 2)
    line = "─" * side + text + "─" * side
    return Text(line[:width], style=theme.style("fg_faint"))
