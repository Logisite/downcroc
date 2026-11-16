"""Hero composite: prominent title, lead, and supporting content."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import heading, prose
from downcroc.cli.design.theme import Theme


class Hero:
    """Hero block composed from primitives."""

    def __init__(
        self,
        title: str,
        lead: str,
        theme: Theme,
        *,
        width: int = 64,
        highlight_title: str = "",
        highlight_body: str = "",
    ) -> None:
        self.title = title
        self.lead = lead
        self.theme = theme
        self.width = width
        self.highlight_title = highlight_title
        self.highlight_body = highlight_body

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [
            heading(self.title, self.theme, level=1),
            prose(self.lead, self.theme, width=self.width, tone="fg_secondary"),
            spacer(1, theme=self.theme),
        ]
        if self.highlight_title or self.highlight_body:
            parts.append(
                Card(
                    self.highlight_title or "highlight",
                    self.highlight_body or "",
                    self.theme,
                    width=min(self.width, 48),
                    border="hairline",
                )
            )
            parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
