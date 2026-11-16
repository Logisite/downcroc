"""Kbd primitive: keyboard shortcut display chip."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def kbd(keys: str | list[str], theme: Theme) -> Text:
    """Render one or more keycaps (shadcn Kbd mapping)."""
    parts = [keys] if isinstance(keys, str) else list(keys)
    out = Text()
    for i, key in enumerate(parts):
        if i:
            out.append(" + ", style=theme.style("fg_faint"))
        out.append(
            f" {key} ", style=theme.style("fg_primary", on="bg_raised", bold=True)
        )
    return out
