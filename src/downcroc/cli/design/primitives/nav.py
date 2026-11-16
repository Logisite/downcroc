"""Navigation atom primitives (visual states)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class NavItem:
    """A navigation row (rail/tree style)."""

    def __init__(
        self,
        label: str,
        theme: Theme,
        *,
        icon: str = "",
        active: bool = False,
        indent: int = 0,
        badge_text: str = "",
    ) -> None:
        self.label = label
        self.theme = theme
        self.icon = icon
        self.active = active
        self.indent = indent
        self.badge_text = badge_text

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        pad = "  " * max(self.indent, 0)
        bg = "bg_selected" if self.active else "bg_page"
        fg = "accent_strong" if self.active else "fg_secondary"
        marker = "▌" if self.active else " "
        line = Text()
        line.append(pad, style=theme.bg(bg))
        line.append(
            marker, style=theme.style("accent" if self.active else "fg_faint", on=bg)
        )
        line.append(" ", style=theme.bg(bg))
        if self.icon:
            line.append(f"{self.icon} ", style=theme.style(fg, on=bg))
        line.append(self.label, style=theme.style(fg, bold=self.active, on=bg))
        if self.badge_text:
            line.append("  ", style=theme.bg(bg))
            line.append(self.badge_text, style=theme.style("fg_faint", on=bg))
        yield line


class TocItem:
    """A table-of-contents entry."""

    def __init__(
        self, label: str, theme: Theme, *, level: int = 1, active: bool = False
    ) -> None:
        self.label = label
        self.theme = theme
        self.level = level
        self.active = active

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        indent = "  " * max(self.level - 1, 0)
        marker = "▸" if self.active else "·"
        tone = "accent_strong" if self.active else "fg_muted"
        line = Text(indent)
        line.append(
            f"{marker} ", style=theme.style("accent" if self.active else "fg_faint")
        )
        line.append(self.label, style=theme.style(tone, bold=self.active))
        yield line
