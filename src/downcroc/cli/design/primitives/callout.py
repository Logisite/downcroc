"""Callout primitive: semantic card with accent bar."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme

TONES = {
    "note": "info",
    "tip": "success",
    "warning": "warning",
    "danger": "danger",
    "example": "accent",
    "quote": "fg_muted",
}


class Callout:
    """A callout: left accent bar, bold label, body text."""

    def __init__(
        self,
        title: str,
        body: str,
        theme: Theme,
        *,
        tone: str = "note",
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.tone = tone

    def _tone_color(self) -> str:
        token = TONES.get(self.tone, "info")
        return getattr(self.theme, token, self.theme.info)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        color = self._tone_color()
        bar = Text("▎ ", style=color)
        title = Text(self.title, style=f"bold {color}")
        yield Text.assemble(bar, title)
        for line in (self.body or "").splitlines() or [""]:
            yield Text(f"  {line}", style=theme.style("fg_secondary"))
        yield Text("")
