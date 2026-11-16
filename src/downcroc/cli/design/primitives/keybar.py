"""Keybar brick: keyboard hints as keycap chips."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def keybar(items: list[tuple[str, str]], theme: Theme) -> Text:
    """Render keycap chips:  enter  open   ?  keys.

    Keys are raised-bg pills in fg_primary, labels muted, separated by
    tokenized gaps. Purely painted; the shell swaps which items are shown.
    """
    out = Text()
    gap = " " * theme.space_3
    for index, (key, hint) in enumerate(items):
        if index:
            out.append(gap, style=theme.style("bg_page"))
        out.append(
            f" {key} ", style=theme.style("fg_primary", on="bg_raised", bold=True)
        )
        out.append(f" {hint}", style=theme.style("fg_muted"))
    return out


def keycap(key: str, theme: Theme) -> Text:
    """A single keycap chip, for use inside other bricks."""
    return Text(f" {key} ", style=theme.style("fg_primary", on="bg_raised", bold=True))
