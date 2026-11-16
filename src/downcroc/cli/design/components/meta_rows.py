"""Meta rows composite for definition/meta display."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class MetaRows:
    """Titled meta/definition rows composed from key-value primitive."""

    def __init__(
        self,
        title: str,
        items: list[tuple[str, str]],
        theme: Theme,
        *,
        divider: bool = True,
        compact: bool = True,
        width: int | None = None,
    ) -> None:
        self.title = title
        self.items = items
        self.theme = theme
        self.divider = divider
        self.compact = compact
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme)]
        parts.append(
            KeyValue(
                self.items,
                self.theme,
                divider=self.divider,
                compact=self.compact,
                width=self.width,
            )
        )
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
