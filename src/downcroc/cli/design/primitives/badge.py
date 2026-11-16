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
    """A compact badge. variant: subtle|solid|outline."""
    color = theme.tone(tone)
    dim = getattr(theme, f"{tone}_dim", theme.bg_raised)
    if variant == "solid":
        return Text(f" {text} ", style=f"bold {theme.accent_fg} on {color}")
    if variant == "outline":
        out = Text("[", style=theme.style("border_strong"))
        out.append(text, style=f"bold {color}")
        out.append("]", style=theme.style("border_strong"))
        return out
    return Text(f" {text} ", style=f"bold {color} on {dim}")
