"""5-zone docs shell scaffold (header, nav, content, outline, footer)."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Static

from downcroc.cli.design.components.pager import Pager
from downcroc.cli.design.docs_ui.nav import StatefulNavWidget
from downcroc.cli.design.docs_ui.outline import ContentOutlinePane
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme


class DocsShell(Vertical):
    """5-zone shell scaffold: header, nav, content+outline, footer (+ pager)."""

    DEFAULT_CSS = """
    DocsShell { height: 1fr; }
    DocsShell > #zone-header { height: auto; border-bottom: solid #232330; padding: 0 1; }
    DocsShell > #zone-body { height: 1fr; }
    DocsShell > #zone-footer { height: auto; border-top: solid #232330; padding: 0 1; }
    #zone-body > #zone-nav { width: 32; height: 1fr; border-right: solid #232330; padding: 0 1; }
    #zone-body > #zone-main { width: 1fr; height: 1fr; }
    """

    def __init__(
        self,
        title: str = "Docs",
        sections: list[tuple[str, str, str]] | None = None,
        theme: Theme = DEFAULT,
        *,
        id: str | None = None,
        on_navigate=None,
    ) -> None:
        super().__init__(id=id)
        self._title = title
        self._sections = sections or [
            ("intro", "Introduction", "Overview and entry point content."),
            ("tokens", "Tokens", "Design tokens and theming details."),
            ("components", "Components", "Primitives and composite building blocks."),
            (
                "interaction",
                "Interaction",
                "State, focus, actions, and scroll behavior.",
            ),
        ]
        self._theme = theme
        self._on_navigate = on_navigate
        self._active_index = 0

    @property
    def sections(self) -> list[tuple[str, str, str]]:
        return list(self._sections)

    @property
    def active_index(self) -> int:
        return self._active_index

    def _pager(self) -> Pager:
        prev_label = prev_target = next_label = next_target = ""
        if self._active_index > 0:
            a, t, _ = self._sections[self._active_index - 1]
            prev_label, prev_target = t, f"/docs/{a}"
        if self._active_index < len(self._sections) - 1:
            a, t, _ = self._sections[self._active_index + 1]
            next_label, next_target = t, f"/docs/{a}"
        return Pager(
            self._theme,
            prev_label=prev_label,
            prev_target=prev_target,
            next_label=next_label,
            next_target=next_target,
            width=60,
            next_state="default",
            prev_state="default",
        )

    def compose(self):
        with Vertical(id="zone-header"):
            yield Static(SectionHeader(self._title, self._theme), id="shell-title")
            yield Static(
                label(
                    "header | nav | content | outline | footer (5-zone scaffold)",
                    self._theme,
                    tone="fg_faint",
                )
            )
        with Horizontal(id="zone-body"):
            with Vertical(id="zone-nav"):
                yield StatefulNavWidget(
                    [
                        (t, {"anchor": a, "icon": "folder"})
                        for a, t, _ in self._sections
                    ],
                    self._theme,
                    active=0,
                    on_navigate=self._on_nav,
                    id="shell-nav",
                )
            with Vertical(id="zone-main"):
                yield ContentOutlinePane(
                    self._sections,
                    self._theme,
                    id="shell-outline",
                    on_active_change=self._on_active,
                )
        with Vertical(id="zone-footer"):
            yield Static(self._pager(), id="shell-pager")
            yield Static(
                Text(
                    "palette/overlay scaffold slot · integrated prev/next links",
                    style=self._theme.style("fg_faint"),
                ),
                id="shell-footer-status",
            )

    def _refresh_pager(self) -> None:
        try:
            pager = self.query_one("#shell-pager", Static)
        except NoMatches:
            return
        pager.update(self._pager())

    def _on_active(self, anchor: str) -> None:
        try:
            nav = self.query_one("#shell-nav", StatefulNavWidget)
        except NoMatches:
            nav = None
        for i, (a, _, _) in enumerate(self._sections):
            if a == anchor:
                self._active_index = i
                if nav is not None:
                    nav.set_active(i, emit=False)
                self._refresh_pager()
                break

    def _on_nav(self, index: int, anchor: str, payload: dict) -> None:
        try:
            pane = self.query_one("#shell-outline", ContentOutlinePane)
        except NoMatches:
            return
        pane.scroll_to_anchor(anchor)
        if self._on_navigate is not None:
            self._on_navigate(index, anchor, payload)
