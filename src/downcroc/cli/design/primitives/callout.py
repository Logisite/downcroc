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
    "info": "info",
    "success": "success",
    "quote": "fg_muted",
}


class Callout:
    """A callout: accent bar, label, and tinted body surface."""

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

    def _tone_token(self) -> str:
        return TONES.get(self.tone, "info")

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        token = self._tone_token()
        color = theme.tone(token)
        dim = getattr(theme, f"{token}_dim", color)
        bar = Text("▎", style=f"{color} on {dim}")
        title = Text(f" {self.title}", style=f"bold {color} on {dim}")
        yield Text.assemble(bar, title)
        for line in (self.body or "").splitlines() or [""]:
            yield Text(f"  {line}  ", style=f"{theme.fg_secondary} on {dim}")
        yield Text("")
