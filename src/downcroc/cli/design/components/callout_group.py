"""Callout group composite: titled collection of callouts."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class CalloutGroup:
    """Group of callouts under a section header."""

    def __init__(
        self,
        title: str,
        callouts: list[Callout],
        theme: Theme,
        *,
        meta: str = "",
    ) -> None:
        self.title = title
        self.callouts = callouts
        self.theme = theme
        self.meta = meta

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme, meta=self.meta)]
        parts.extend(self.callouts)
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
