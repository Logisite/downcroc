"""Toast/pill feedback primitive (static render)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class Toast:
    """A compact toast pill. Timing/dismiss behavior is deferred to interaction."""

    def __init__(
        self,
        message: str,
        theme: Theme,
        *,
        tone: str = "info",
        icon: str = "",
    ) -> None:
        self.message = message
        self.theme = theme
        self.tone = tone
        self.icon = icon

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        color = theme.tone(self.tone)
        dim = getattr(theme, f"{self.tone}_dim", theme.bg_raised)
        pill = Text()
        pill.append(" ", style=f"{color} on {dim}")
        glyph = self.icon or {"success": "✓", "warning": "!", "danger": "×"}.get(
            self.tone, "i"
        )
        pill.append(f"{glyph} ", style=f"bold {color} on {dim}")
        pill.append(self.message, style=f"{theme.fg_primary} on {dim}")
        pill.append(" ", style=f"{color} on {dim}")
        yield pill
        yield Text("")
