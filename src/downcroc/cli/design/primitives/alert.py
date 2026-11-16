"""Alert primitive (shadcn Alert mapping): title + description with tone."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.padding import Padding
from rich.text import Text

from downcroc.cli.design.primitives.icon import resolve_icon
from downcroc.cli.design.theme import DEFAULT, Theme

TONES = {
    "default": "accent",
    "info": "info",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
    "destructive": "danger",
    "note": "info",
}


class Alert:
    """Alert box: icon/tone bar, title, and description."""

    def __init__(
        self,
        title: str,
        description: str | RenderableType = "",
        theme: Theme | None = None,
        *,
        tone: str = "default",
        icon: str | None = None,
        width: int | None = None,
    ) -> None:
        self.title = title
        self.description = description
        self.theme = theme or DEFAULT
        self.tone = tone
        self.icon = icon
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        tone_key = TONES.get(self.tone, self.tone)
        color = theme.tone(tone_key)
        dim = getattr(theme, f"{tone_key}_dim", theme.bg_raised)
        width = min(self.width or options.max_width, options.max_width)
        default_icon = {
            "warning": "warning",
            "danger": "danger",
            "success": "success",
        }.get(tone_key, "info")
        glyph = resolve_icon(self.icon or default_icon)
        header = Text()
        header.append(f" {glyph} ", style=f"bold {color} on {dim}")
        header.append(
            f" {self.title} ",
            style=theme.style("fg_primary", bold=True, on=dim),
        )
        header.append(" " * max(width - len(header.plain), 0), style=f"on {dim}")
        yield header
        if self.description:
            body = (
                Text(self.description, style=theme.style("fg_secondary"))
                if isinstance(self.description, str)
                else self.description
            )
            yield Padding(
                Group(body) if not isinstance(body, Text) else body, (0, 1, 0, 2)
            )
        yield Text("")
