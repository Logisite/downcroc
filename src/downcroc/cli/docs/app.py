from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Static, Tree

from downcroc.cli.docs import clipboard, model, search
from downcroc.cli.docs.render import page_renderable
from downcroc.version import __version__


class DocsApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #title { dock: top; height: 1; background: $accent; color: $text; padding: 0 1; }
    #body { height: 1fr; }
    #sidebar { width: 34; border-right: solid $accent; }
    #content { width: 1fr; padding: 0 2; }
    #toc { width: 32; border-left: solid $accent; padding: 0 1; }
    #search { dock: bottom; height: 3; display: none; }
    #search.visible { display: block; }
    #footer { dock: bottom; height: 1; background: $boost; color: $text-muted; padding: 0 1; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "quit"),
        Binding("slash", "search", "search"),
        Binding("ctrl+k", "search", "search"),
        Binding("c", "copy", "copy page"),
        Binding("o", "open", "browser"),
        Binding("r", "raw", "raw"),
        Binding("t", "change_theme", "theme"),
        Binding("question_mark", "help", "keys"),
    ]

    def __init__(self, pages: list[model.Page]) -> None:
        super().__init__()
        self.pages = pages
        self.current = next(
            (page for page in pages if page.rel == "index.md"),
            pages[0] if pages else None,
        )
        self.raw = False

    def compose(self) -> ComposeResult:
        yield Static(f" downcroc docs  {__version__}", id="title")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Tree("Documentation", id="nav")
                yield Input(placeholder="Search docs", id="search")
            with VerticalScroll(id="content"):
                yield Static("", id="page")
            yield Static("", id="toc")
        yield Static(
            " / search   c copy   o browser   r raw   t theme   ? keys   q quit",
            id="footer",
        )

    def on_mount(self) -> None:
        tree = self.query_one("#nav", Tree)
        tree.show_root = True
        groups: dict[str, object] = {}
        for page in self.pages:
            parts = page.rel.split("/")
            parent = groups.get(parts[0])
            if len(parts) == 1:
                tree.root.add_leaf(page.title, data=page)
                continue
            if parent is None:
                parent = tree.root.add(parts[0].replace("-", " ").title(), expand=True)
                groups[parts[0]] = parent
            parent.add_leaf(page.title, data=page)
        tree.root.expand()
        self._show()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if isinstance(event.node.data, model.Page):
            self.current = event.node.data
            self._show()

    def _show(self) -> None:
        page = self.current
        if page is None:
            return
        width = max(40, self.size.width - (66 if self.size.width >= 120 else 36))
        body = page.raw if self.raw else page.body
        shown = model.Page(
            path=page.path,
            rel=page.rel,
            title=page.title,
            description=page.description,
            body=body,
            tags=page.tags,
            audience=page.audience,
            status=page.status,
            since=page.since,
            order=page.order,
            summary=page.summary,
            max_width=page.max_width,
            toc=page.toc,
            search_boost=page.search_boost,
            headings=page.headings,
        )
        self.query_one("#page", Static).update(page_renderable(shown, width))
        toc = Text("On this page\n", style="bold")
        for heading in page.headings:
            toc.append(f"\n {heading}", style="dim")
        self.query_one("#toc", Static).update(toc)
        self.query_one("#toc", Static).display = self.size.width >= 120

    def on_resize(self) -> None:
        self._show()

    def action_search(self) -> None:
        field = self.query_one("#search", Input)
        field.add_class("visible")
        field.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.remove_class("visible")
        hits = search.search(self.pages, event.value)
        if hits:
            self.current = hits[0].page
            self._show()
            self.notify(f"{len(hits)} matches, opened {hits[0].page.title}")
        else:
            self.notify("no matches")

    def action_copy(self) -> None:
        if self.current is None:
            return
        copied = clipboard.copy(self.current.raw)
        self.notify("page copied" if copied else "clipboard unavailable, use --raw")

    def action_open(self) -> None:
        if self.current is None:
            return
        webbrowser.open(Path(self.current.path).as_uri())

    def action_raw(self) -> None:
        self.raw = not self.raw
        self._show()

    def action_help(self) -> None:
        self.notify("/ search  c copy  o browser  r raw  t theme  q quit")
