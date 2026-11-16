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
        width: int | None = None,
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.tone = tone
        self.width = width

    def _tone_token(self) -> str:
        return TONES.get(self.tone, "info")

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        token = self._tone_token()
        color = theme.tone(token)
        dim = getattr(theme, f"{token}_dim", color)
        width = self.width or min(options.max_width, 60)
        inner = max(width - 1, 10)

        bar = Text("▎", style=f"{color} on {dim}")
        title = Text(f" {self.title}".ljust(inner), style=f"bold {color} on {dim}")
        yield Text.assemble(bar, title)

        lines = (self.body or "").splitlines() or [""]
        for line in lines:
            body_text = f"  {line}".ljust(inner)
            yield Text.assemble(
                Text(" ", style=f"{color} on {dim}"),
                Text(body_text, style=f"{theme.fg_secondary} on {dim}"),
            )
        yield Text("")
