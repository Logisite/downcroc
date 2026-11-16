"""Badge primitive: small status/label chips."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def badge(
    text: str,
    theme: Theme,
    *,
    tone: str = "accent",
    variant: str = "subtle",
) -> Text:
    """A compact badge. variant: subtle|solid."""
    color = theme.tone(tone)
    dim = getattr(theme, f"{tone}_dim", theme.bg_raised)
    if variant == "solid":
        return Text(f" {text} ", style=f"bold {theme.accent_fg} on {color}")
    return Text(f" {text} ", style=f"bold {color} on {dim}")
