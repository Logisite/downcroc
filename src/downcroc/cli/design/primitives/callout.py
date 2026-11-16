"""Callout primitive: semantic card with accent bar."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.primitives.icon import resolve_icon
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
        icon: str = "",
        width: int | None = None,
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.tone = tone
        self.icon = icon
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

        icon = resolve_icon(self.icon) if self.icon else ""
        label = f"{icon} {self.title}" if icon else self.title
        bar = Text("▎", style=f"{color} on {dim}")
        title = Text(f" {label}".ljust(inner), style=f"bold {color} on {dim}")
        yield Text.assemble(bar, title)

        body = Text(self.body or "", style=f"{theme.fg_secondary} on {dim}")
        for line in body.wrap(console, max(inner - 2, 8), overflow="fold"):
            padded = Text("  ", style=f"{theme.fg_secondary} on {dim}")
            padded.append_text(line)
            pad_len = inner - len(padded.plain)
            if pad_len > 0:
                padded.append(" " * pad_len, style=f"{theme.fg_secondary} on {dim}")
            yield Text.assemble(Text(" ", style=f"{color} on {dim}"), padded)
        yield Text("")
