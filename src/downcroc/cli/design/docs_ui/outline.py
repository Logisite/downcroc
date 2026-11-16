"""Content + outline composition with scroll-spy-like active tracking."""

from __future__ import annotations

from textual import events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from downcroc.cli.design.docs_ui.sections import AnchoredSectionWidget
from downcroc.cli.design.docs_ui.toc import StatefulTocWidget
from downcroc.cli.design.interaction.scroll import scroll_to_widget
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.theme import DEFAULT, Theme


class ContentOutlinePane(Horizontal):
    """Main content + TOC outline; TOC clicks scroll, scroll updates active anchor."""

    DEFAULT_CSS = """
    ContentOutlinePane { height: 1fr; }
    ContentOutlinePane > #doc-content { width: 1fr; height: 1fr; }
    ContentOutlinePane > #doc-outline {
        width: 32; height: 1fr; border-left: solid #232330; padding: 0 1;
    }
    """

    def __init__(
        self,
        sections: list[tuple[str, str, str]],
        theme: Theme = DEFAULT,
        *,
        id: str | None = None,
        on_active_change=None,
    ) -> None:
        super().__init__(id=id)
        self._sections = sections  # (anchor, title, body)
        self._theme = theme
        self._active_anchor = sections[0][0] if sections else None
        self._on_active_change = on_active_change

    @property
    def active_anchor(self) -> str | None:
        return self._active_anchor

    def compose(self):
        with VerticalScroll(id="doc-content"):
            for anchor, title, body in self._sections:
                yield AnchoredSectionWidget(
                    anchor, title, body, self._theme, id=f"sec-{anchor}"
                )
        with Vertical(id="doc-outline"):
            yield Static(SectionHeader("On this page", self._theme))
            yield StatefulTocWidget(
                [
                    (title, {"anchor": anchor, "level": 1})
                    for anchor, title, _ in self._sections
                ],
                self._theme,
                active_anchor=self._active_anchor,
                on_navigate=self._on_toc_navigate,
                id="toc-widget",
            )

    def _on_toc_navigate(self, _index: int, anchor: str, _payload: dict) -> None:
        try:
            section = self.query_one(f"#sec-{anchor}", AnchoredSectionWidget)
            container = self.query_one("#doc-content", VerticalScroll)
            toc = self.query_one("#toc-widget", StatefulTocWidget)
        except NoMatches:
            return
        scroll_to_widget(container, section)
        self._set_active(anchor)
        toc.set_active_anchor(anchor)

    def _set_active(self, anchor: str | None) -> None:
        if anchor == self._active_anchor:
            return
        self._active_anchor = anchor
        if self._on_active_change is not None and anchor is not None:
            self._on_active_change(anchor)

    def _update_active_from_scroll(self) -> None:
        try:
            container = self.query_one("#doc-content", VerticalScroll)
            toc = self.query_one("#toc-widget", StatefulTocWidget)
        except NoMatches:
            return
        scroll_y = getattr(container, "scroll_y", 0)
        active = self._active_anchor
        for anchor, _, _ in self._sections:
            try:
                widget = self.query_one(f"#sec-{anchor}", AnchoredSectionWidget)
            except NoMatches:
                continue
            region = getattr(widget, "virtual_region", None) or getattr(
                widget, "region", None
            )
            top = getattr(region, "y", 0) if region is not None else 0
            if top - scroll_y <= 2:
                active = anchor
        if active is not None:
            self._set_active(active)
            toc.set_active_anchor(active)

    def on_mouse_scroll_up(self, _: events.MouseScrollUp) -> None:
        self.call_after_refresh(self._update_active_from_scroll)

    def on_mouse_scroll_down(self, _: events.MouseScrollDown) -> None:
        self.call_after_refresh(self._update_active_from_scroll)

    def on_scroll(self, _: events.Scroll) -> None:
        self.call_after_refresh(self._update_active_from_scroll)

    def scroll_to_anchor(self, anchor: str) -> None:
        self._on_toc_navigate(-1, anchor, {"anchor": anchor})
