"""Anchored/structural doc sections for content+outline composition."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static

from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.text import label, prose
from downcroc.cli.design.theme import DEFAULT, Theme


class AnchoredSectionWidget(Vertical):
    """Content section with an anchor id for scroll-spy/TOC targeting."""

    def __init__(
        self,
        anchor: str,
        title: str,
        body: str,
        theme: Theme = DEFAULT,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.anchor = anchor
        self._title = title
        self._body = body
        self._theme = theme

    def compose(self):
        yield Static(SectionHeader(self._title, self._theme), id=f"hdr-{self.anchor}")
        yield Static(label(f"#{self.anchor}", self._theme, tone="fg_faint"))
        yield Static(prose(self._body, self._theme, width=60))
        yield Static(Text(" "))
