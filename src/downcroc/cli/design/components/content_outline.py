"""Content + outline composition (structural, no scroll-spy wiring)."""

from __future__ import annotations

from rich.columns import Columns
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.panel import Panel

from downcroc.cli.design.primitives.nav import TocItem
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class ContentOutline:
    """Compose main content with a TOC/outline sidebar area."""

    def __init__(
        self,
        content: object | list[object],
        outline_items: list[tuple[str, dict]],
        theme: Theme,
        *,
        outline_title: str = "On this page",
        outline_width: int = 28,
        active: str | None = None,
    ) -> None:
        self.content = content if isinstance(content, list) else [content]
        self.outline_items = outline_items
        self.theme = theme
        self.outline_title = outline_title
        self.outline_width = outline_width
        self.active = active

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        outline_parts: list[object] = [
            SectionHeader(self.outline_title, self.theme),
        ]
        for text, opts in self.outline_items:
            anchor = str(opts.get("anchor", text))
            state = (
                "active"
                if self.active and anchor == self.active
                else str(opts.get("state", "default"))
            )
            outline_parts.append(
                TocItem(
                    text,
                    self.theme,
                    level=int(opts.get("level", 1)),
                    active=bool(opts.get("active", False)) or state == "active",
                    state=state if state != "active" else "default",
                )
            )
        outline_parts.append(spacer(1, theme=self.theme))
        outline = Panel(
            Group(*outline_parts),
            width=self.outline_width,
            border_style=self.theme.style("border_subtle"),
            padding=(0, 1),
        )
        main = Group(*self.content)
        yield Columns([main, outline], expand=True, equal=False, align="left")
