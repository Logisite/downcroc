"""Empty state primitive."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class EmptyState:
    """A calm empty/no-data state."""

    def __init__(
        self,
        title: str,
        theme: Theme,
        *,
        body: str = "",
        icon: str = "∅",
    ) -> None:
        self.title = title
        self.theme = theme
        self.body = body
        self.icon = icon

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        head = Text()
        head.append(f"{self.icon} ", style=theme.style("fg_faint"))
        head.append(self.title, style=theme.style("fg_muted", bold=True))
        yield head
        if self.body:
            yield Text(f"  {self.body}", style=theme.style("fg_faint"))
        yield Text("")
