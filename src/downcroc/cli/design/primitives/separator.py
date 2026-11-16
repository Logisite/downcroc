"""Separator primitive (shadcn Separator mapping)."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def separator(
    theme: Theme, *, orientation: str = "horizontal", length: int = 40
) -> Text:
    """Horizontal or vertical separator line."""
    if orientation == "vertical":
        return Text("│", style=theme.style("border_subtle"))
    length = max(length, 1)
    return Text("─" * length, style=theme.style("border_subtle"))
