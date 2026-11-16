"""Section header primitive."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class SectionHeader:
    """A titled section break with optional meta text."""

    def __init__(
        self,
        title: str,
        theme: Theme,
        *,
        meta: str = "",
        width: int | None = None,
        rule: bool = True,
    ) -> None:
        self.title = title
        self.theme = theme
        self.meta = meta
        self.width = width
        self.rule = rule

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        width = min(self.width or options.max_width, options.max_width)
        line = Text()
        line.append(self.title, style=theme.style("fg_secondary", bold=True))
        if self.meta:
            line.append(" " * theme.space_2, style=theme.style("bg_page"))
            line.append(self.meta, style=theme.style("fg_faint"))
        yield line
        if self.rule:
            rule_len = min(max(width, 8), max(len(line.plain), 16))
            yield Text("─" * rule_len, style=theme.style("border_subtle"))
        yield Text("")
