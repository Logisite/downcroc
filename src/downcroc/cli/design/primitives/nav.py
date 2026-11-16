"""Navigation atom primitives (visual states)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.primitives.icon import resolve_icon
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
        width: int | None = None,
        state: str = "default",
    ) -> None:
        self.label = label
        self.theme = theme
        self.icon = icon
        self.active = active
        self.indent = indent
        self.badge_text = badge_text
        self.width = width
        self.state = state

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        pad = "  " * max(self.indent, 0)
        state = "active" if self.active and self.state == "default" else self.state
        bg = "bg_panel"
        fg = "fg_secondary"
        marker = "│"
        marker_tone = "border_subtle"
        bold = False
        if state == "active":
            bg, fg, marker, marker_tone, bold = (
                "bg_selected",
                "accent_strong",
                "▌",
                "accent",
                True,
            )
        elif state == "hover":
            bg, fg = "bg_hover", "fg_primary"
        elif state == "focus":
            bg, fg, marker_tone = "bg_hover", "accent_strong", "border_focus"
        elif state == "disabled":
            bg, fg, marker_tone = "bg_panel", "fg_faint", "border_hairline"

        width = min(self.width or options.max_width, options.max_width)
        left = Text()
        left.append(pad, style=theme.bg(bg))
        left.append(marker, style=theme.style(marker_tone, on=bg))
        left.append(" ", style=theme.bg(bg))
        icon_slot = f"{resolve_icon(self.icon)} " if self.icon else "  "
        left.append(icon_slot, style=theme.style(fg, on=bg))
        left.append(self.label, style=theme.style(fg, bold=bold, on=bg))
        right = Text()
        if self.badge_text:
            right.append(self.badge_text, style=theme.style("fg_faint", on=bg))
            right.append(" ", style=theme.bg(bg))
        fill = width - len(left.plain) - len(right.plain)
        fill = max(fill, 1)
        line = Text()
        line.append_text(left)
        line.append(" " * fill, style=theme.bg(bg))
        line.append_text(right)
        yield line


class TocItem:
    """A table-of-contents entry."""

    def __init__(
        self,
        label: str,
        theme: Theme,
        *,
        level: int = 1,
        active: bool = False,
        state: str = "default",
    ) -> None:
        self.label = label
        self.theme = theme
        self.level = level
        self.active = active
        self.state = state

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        indent = "  " * max(self.level - 1, 0)
        state = "active" if self.active and self.state == "default" else self.state
        marker = "▸" if state == "active" else "·"
        tone = "accent_strong" if state == "active" else "fg_muted"
        marker_tone = "accent" if state == "active" else "fg_faint"
        if state == "hover":
            tone, marker_tone = "fg_primary", "fg_muted"
        elif state == "focus":
            tone, marker_tone = "accent_strong", "border_focus"
        line = Text(indent)
        line.append(f"{marker} ", style=theme.style(marker_tone))
        line.append(self.label, style=theme.style(tone, bold=(state == "active")))
        yield line
