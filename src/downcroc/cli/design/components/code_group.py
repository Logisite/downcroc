"""Code group composite: titled collection of code panels."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.code_panel import CodePanel
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class CodeGroup:
    """Group of code panels under a section header."""

    def __init__(
        self,
        title: str,
        panels: list[CodePanel],
        theme: Theme,
        *,
        meta: str = "",
    ) -> None:
        self.title = title
        self.panels = panels
        self.theme = theme
        self.meta = meta

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme, meta=self.meta)]
        for i, panel in enumerate(self.panels):
            parts.append(panel)
            if i < len(self.panels) - 1:
                parts.append(spacer(1, theme=self.theme))
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
