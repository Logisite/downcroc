"""Doc header variants composed for docs layouts."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.components.breadcrumb_bar import BreadcrumbBar
from downcroc.cli.design.components.meta_bar import MetaBar
from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import heading, prose
from downcroc.cli.design.theme import Theme


class DocHeader:
    """Richer doc header: breadcrumb, title/lead, meta row, divider."""

    def __init__(
        self,
        title: str,
        theme: Theme,
        *,
        breadcrumb_items: list[str] | list[tuple[str, str]] | None = None,
        lead: str = "",
        meta: list[tuple[str, str]] | None = None,
        width: int = 72,
    ) -> None:
        self.title = title
        self.theme = theme
        self.breadcrumb_items = breadcrumb_items or []
        self.lead = lead
        self.meta = meta or []
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = []
        if self.breadcrumb_items:
            parts.append(BreadcrumbBar(self.breadcrumb_items, self.theme))
        parts.append(heading(self.title, self.theme, level=1))
        if self.lead:
            parts.append(
                prose(self.lead, self.theme, width=self.width, tone="fg_secondary")
            )
        if self.meta:
            parts.append(MetaBar(self.meta, self.theme))
        parts.append(divider(self.theme, width=min(self.width, options.max_width)))
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
