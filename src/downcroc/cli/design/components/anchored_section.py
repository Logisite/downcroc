"""Anchored section composite (structural id/anchor, no routing)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import Theme


class AnchoredSection:
    """Section with an explicit anchor id for TOC/scroll targeting."""

    def __init__(
        self,
        anchor: str,
        title: str,
        content: object | list[object],
        theme: Theme,
        *,
        level: int = 2,
        meta: str = "",
        show_anchor: bool = True,
    ) -> None:
        self.anchor = anchor
        self.title = title
        self.content = content if isinstance(content, list) else [content]
        self.theme = theme
        self.level = level
        self.meta = meta
        self.show_anchor = show_anchor

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme, meta=self.meta)]
        if self.show_anchor:
            parts.append(label(f"#{self.anchor}", self.theme, tone="fg_faint"))
        parts.extend(self.content)
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
