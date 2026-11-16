"""Tooltip primitive (shadcn Tooltip mapping, render hint)."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def tooltip_hint(label: str, hint: str, theme: Theme) -> Text:
    """Inline label with a muted tooltip/hint (TUI approximation)."""
    out = Text(label, style=theme.style("fg_secondary"))
    out.append(f" ({hint})", style=theme.style("fg_faint"))
    return out
