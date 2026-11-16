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
        compact: bool = False,
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.tone = tone
        self.icon = icon
        self.width = width
        self.compact = compact

    def _tone_token(self) -> str:
        return TONES.get(self.tone, "info")

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        token = self._tone_token()
        color = theme.tone(token)
        dim = getattr(theme, f"{token}_dim", theme.bg_panel)
        width = self.width or min(options.max_width, 60)
        inner = max(width - 1, 10)

        default_icon = {
            "info": "info",
            "success": "success",
            "warning": "warning",
            "danger": "danger",
            "accent": "info",
            "fg_muted": "dot",
        }.get(token, "")
        icon = (
            resolve_icon(self.icon or default_icon)
            if (self.icon or default_icon)
            else ""
        )
        label = f"{icon} {self.title}" if icon else self.title
        bar = Text("▎", style=f"{color} on {dim}")
        title = Text(f" {label}".ljust(inner), style=f"bold {color} on {dim}")
        yield Text.assemble(bar, title)

        body_style = f"{theme.fg_secondary} on {dim}"
        body = Text(self.body or "", style=body_style)
        indent = " " * theme.space_2
        wrap_width = max(inner - (theme.space_2 + 1), 8)
        for line in body.wrap(console, wrap_width, overflow="fold"):
            padded = Text(indent, style=body_style)
            padded.append_text(line)
            pad_len = inner - len(padded.plain)
            if pad_len > 0:
                padded.append(" " * pad_len, style=body_style)
            yield Text.assemble(Text(" ", style=f"{color} on {dim}"), padded)
        if not self.compact:
            yield Text("")
