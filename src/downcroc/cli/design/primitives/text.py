"""Text bricks: styled runs of glyphs, painted from theme tokens."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def heading(text: str, theme: Theme, *, level: int = 1) -> Text:
    """Section heading: bold, primary fg, with a dim accent bar for h2+."""
    if level <= 1:
        return Text(text, style=theme.style("fg_primary", bold=True))
    bar = Text("▏", style=theme.style("accent_dim"))
    bar.append(" ", style=theme.style("bg_page"))
    bar.append(text, style=theme.style("fg_primary", bold=True))
    return bar


def label(text: str, theme: Theme) -> Text:
    """Small caps-style label for nav and section markers."""
    spaced = " ".join(text)
    return Text(spaced.upper(), style=theme.style("fg_muted"))


def chip(text: str, theme: Theme, *, tone: str = "bg_raised") -> Text:
    """Inline chip: rounded-paren pill with a stepped background."""
    out = Text()
    out.append("(", style=theme.style("fg_faint", on=tone))
    out.append(text, style=theme.style("fg_primary", on=tone))
    out.append(")", style=theme.style("fg_faint", on=tone))
    return out


def prose(text: str, theme: Theme) -> Text:
    """Body text: the 4-step fg discipline means never pure white."""
    return Text(text, style=theme.style("fg_primary"))
