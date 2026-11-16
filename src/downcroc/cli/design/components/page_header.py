"""Page header composite: title, lead/meta, and divider."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text

from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import heading, prose
from downcroc.cli.design.theme import Theme


class PageHeader:
    """Top-of-page header composed from text/rule primitives."""

    def __init__(
        self,
        title: str,
        theme: Theme,
        *,
        subtitle: str = "",
        meta: str = "",
        width: int = 60,
    ) -> None:
        self.title = title
        self.theme = theme
        self.subtitle = subtitle
        self.meta = meta
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [heading(self.title, self.theme, level=1)]
        if self.subtitle:
            parts.append(
                prose(self.subtitle, self.theme, width=self.width, tone="fg_muted")
            )
        if self.meta:
            parts.append(Text(self.meta, style=self.theme.style("fg_faint")))
        parts.append(divider(self.theme, width=min(self.width, options.max_width)))
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
