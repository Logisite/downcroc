from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from downcroc.cli.docs import clipboard, model, search
from downcroc.cli.docs.render import page_renderable
from downcroc.cli.docs.theme import DOCS_THEME
from downcroc.version import __version__

WIDE = 140
MEDIUM = 100
NARROW = 60


class NavScreen(ModalScreen[model.Page]):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "close")]

    def __init__(self, pages: list[model.Page], current: model.Page | None) -> None:
        super().__init__()
        self.pages = pages
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="nav-modal"):
            yield Static("Documentation", classes="nav-heading")
            yield OptionList(id="nav-options")

    def on_mount(self) -> None:
        _fill_options(self.query_one("#nav-options", OptionList), self.pages)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            page = next(
                (page for page in self.pages if page.rel == event.option.id), None
            )
            if page is not None:
                self.dismiss(page)


class DocsApp(App[None]):
    TITLE = "downcroc docs"
    CSS = """
    Screen { layout: vertical; background: $surface; }
    #topbar { dock: top; height: 1; background: $accent; color: $text; padding: 0 1; }
    #workspace { height: 1fr; }
    #sidebar { width: 32; border-right: solid $accent; padding: 0 1; }
    OptionList { background: transparent; border: none; padding: 0; }
    OptionList > .option-list--option { padding: 0 1; }
    OptionList > .option-list--option-highlighted { background: $accent 30%; color: $text; }
    #content { width: 1fr; padding: 0 2; }
    #toc { width: 30; border-left: solid $accent; padding: 0 1; }
    #search { dock: bottom; height: 3; display: none; }
    #search.visible { display: block; }
    #footer { dock: bottom; height: 1; background: $boost; color: $text-muted; padding: 0 1; }
    #topbar.narrow { padding: 0; }
    #content.narrow { padding: 0 1; }
    #content.tiny { padding: 0; }
    #nav-modal { width: 40; height: 80%; background: $panel; border: solid $accent; padding: 1; }
    .nav-heading { text-style: bold; padding: 0 0 1 0; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "quit"),
        Binding("m", "menu", "menu"),
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
        self._wide = True
        self._medium = True

    def compose(self) -> ComposeResult:
        yield Static("", id="topbar")
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield OptionList(id="nav")
            with VerticalScroll(id="content"):
                yield Static("", id="page")
            yield Static("", id="toc")
        yield Input(placeholder="Search docs", id="search")
        yield Static("", id="footer")

    def on_mount(self) -> None:
        self.register_theme(DOCS_THEME)
        self.theme = "downcroc"
        _fill_options(self.query_one("#nav", OptionList), self.pages)
        self._layout()
        self._show()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            page = next(
                (page for page in self.pages if page.rel == event.option.id), None
            )
            if page is not None:
                self.current = page
                self._show()

    def _layout(self) -> None:
        width = self.size.width
        self._wide = width >= WIDE
        self._medium = width >= MEDIUM
        sidebar = self.query_one("#sidebar")
        toc = self.query_one("#toc")
        sidebar.display = self._medium
        toc.display = self._wide
        content = self.query_one("#content")
        content.set_class(width < NARROW, "tiny")
        content.set_class(width < MEDIUM, "narrow")
        self.query_one("#topbar").set_class(width < MEDIUM, "narrow")
        self._footer(width)

    def _footer(self, width: int) -> None:
        if width < MEDIUM:
            text = " m menu   / search   c copy   o browser   r raw   ? keys   q quit"
        else:
            text = " / search   c copy   o browser   r raw   t theme   ? keys   q quit"
        self.query_one("#footer", Static).update(Text(text, style="dim"))

    def _top(self, page: model.Page) -> Text:
        title = Text()
        title.append(" ◆ downcroc docs", style="bold")
        if self.size.width >= MEDIUM:
            crumb = "Home" if page.rel == "index.md" else page.rel.removesuffix(".md")
            title.append(f"   {crumb}", style="dim")
            title.append(f"   v{__version__}", style="dim")
        else:
            title.append("   ☰", style="dim")
        return title

    def _content_width(self) -> int:
        width = self.size.width
        if self._wide:
            width -= 32 + 30 + 4
        elif self._medium:
            width -= 32 + 4
        else:
            width -= 2
        return max(32, width)

    def _show(self) -> None:
        page = self.current
        if page is None:
            return
        self.query_one("#topbar", Static).update(self._top(page))
        shown = model.Page(
            path=page.path,
            rel=page.rel,
            title=page.title,
            description=page.description,
            body=page.raw if self.raw else page.body,
            tags=page.tags,
            audience=page.audience,
            status=page.status,
            since=page.since,
            order=page.order,
            summary=page.summary,
            max_width=page.max_width,
            toc=False,
            search_boost=page.search_boost,
            headings=page.headings,
        )
        self.query_one("#page", Static).update(
            page_renderable(shown, self._content_width())
        )
        toc = Text("On this page\n", style="bold")
        for heading in page.headings:
            toc.append(f"\n {heading}", style="dim")
        self.query_one("#toc", Static).update(toc)
        self._footer(self.size.width)

    def on_resize(self) -> None:
        self._layout()
        self._show()

    def action_menu(self) -> None:
        if self._medium:
            self.query_one("#nav", OptionList).focus()
            return
        self.push_screen(
            NavScreen(self.pages, self.current),
            self._opened_from_menu,
        )

    def _opened_from_menu(self, page: model.Page | None) -> None:
        if page is not None:
            self.current = page
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
        self.notify("/ search  c copy  o browser  r raw  t theme  m menu  q quit")


def _fill_options(widget: OptionList, pages: list[model.Page]) -> None:
    widget.clear_options()
    section = None
    for page in pages:
        current = page.rel.split("/", 1)[0] if "/" in page.rel else ""
        if current != section:
            section = current
            label = section.replace("-", " ").upper() if section else "HOME"
            widget.add_option(Option(label, id=None, disabled=True))
        widget.add_option(Option(f"  {page.title}", id=page.rel))
