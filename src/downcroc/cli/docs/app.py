"""Interactive docs app (Phase 4): 5-zone shell, palette, routing, actions."""

from __future__ import annotations

import os
import shlex
import subprocess
import webbrowser
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from downcroc.cli.design.docs_ui.toc import StatefulTocWidget
from downcroc.cli.design.theme import DEFAULT
from downcroc.cli.design.widgets import PrimitiveAction
from downcroc.cli.docs import clipboard, model
from downcroc.cli.docs.content.index import DocIndex, IndexedPage, build_index
from downcroc.cli.docs.content.parser import parse_document
from downcroc.cli.docs.md_render import render_page as render_page_v2
from downcroc.cli.docs.overlays import CommandPaletteScreen, HelpScreen, PaletteItem
from downcroc.cli.docs.shell import (
    DOCS_SHELL_CSS,
    BreadcrumbNavigate,
    DocsShell,
    HeadingCopyLink,
    PagerNavigate,
    SidebarNavigate,
    TopbarActionActivate,
    fill_nav,
    fill_toc,
)
from downcroc.cli.docs.theme import DOCS_THEME

WIDE = 120
MEDIUM = 92


class NavScreen(ModalScreen[IndexedPage | model.Page | None]):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss_none", "close")]
    DEFAULT_CSS = """
    NavScreen { align: center middle; background: black 35%; }
    #dc-nav-modal { width: 50; height: 80%; background: $panel; border: tall $accent 40%; padding: 1; }
    """

    def __init__(self, pages) -> None:
        super().__init__()
        self.pages = pages

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="dc-nav-modal"):
            yield Static("Documentation")
            yield OptionList(id="dc-nav-options")

    def on_mount(self) -> None:
        fill_nav(self.query_one("#dc-nav-options", OptionList), self.pages)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option.id:
            return
        page = _find_by_id(self.pages, event.option.id)
        self.dismiss(page)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class DocsApp(App[None]):
    TITLE = "downcroc docs"
    CSS = DOCS_SHELL_CSS
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "quit"),
        Binding("m", "menu", "menu"),
        Binding("slash", "palette", "search"),
        Binding("ctrl+k", "palette", "palette"),
        Binding("c", "copy", "copy page"),
        Binding("y", "copy_link", "copy link"),
        Binding("o", "open", "open"),
        Binding("r", "raw", "raw"),
        Binding("e", "edit", "editor"),
        Binding("t", "cycle_theme", "theme"),
        Binding("question_mark", "help", "help"),
        Binding("[", "prev_page", "prev"),
        Binding("]", "next_page", "next"),
        Binding("escape", "close_overlay", "close", show=False),
    ]

    def __init__(self, pages: list[model.Page]) -> None:
        super().__init__()
        self.legacy_pages = pages
        self.index: DocIndex | None = _try_build_index(pages)
        self.pages = list(self.index.pages) if self.index else list(pages)
        self.current = _initial_page(self.pages, self.index)
        self.raw = False
        self._history: list[str] = []
        self._overlay_open = False

    def compose(self) -> ComposeResult:
        yield DocsShell(id="dc-docs-root")

    @property
    def shell(self) -> DocsShell:
        return self.query_one("#dc-docs-root", DocsShell)

    def on_mount(self) -> None:
        self.register_theme(DOCS_THEME)
        self.theme = "downcroc"
        try:
            self.shell.set_sidebar(
                self.pages, active_route=self._route(self.current), theme=DEFAULT
            )
        except AttributeError, NoMatches:
            try:
                nav = self.query_one("#dc-nav", OptionList)
                fill_nav(nav, self.pages, active_route=self._route(self.current))
            except NoMatches:
                pass
        self._layout()
        self._show()

    def on_resize(self) -> None:
        self._layout()
        # avoid full content/TOC/nav rebuild on every resize (causes flicker/duplicates)
        self._update_keybar()

    def _layout(self) -> None:
        width = self.size.width
        show_sidebar = width >= MEDIUM
        show_outline = width >= 118
        self.query_one("#dc-sidebar").display = show_sidebar
        self.query_one("#dc-outline").display = show_outline
        self._update_keybar()

    def _update_keybar(self) -> None:
        hints = [
            ("/", "search"),
            ("ctrl+k", "palette"),
            ("[ ]", "prev/next"),
            ("c", "copy"),
            ("y", "link"),
            ("o", "open"),
            ("e", "edit"),
            ("r", "raw"),
            ("?", "help"),
            ("q", "quit"),
        ]
        if self.size.width < MEDIUM:
            hints = [
                ("m", "menu"),
                ("/", "search"),
                ("c", "copy"),
                ("y", "link"),
                ("q", "quit"),
            ]
        self.shell.set_keybar(hints, DEFAULT)

    def _route(self, page) -> str:
        if page is None:
            return ""
        if isinstance(page, IndexedPage):
            return page.route or ""
        rel = page.rel.removesuffix(".md")
        return "" if rel == "index" else rel

    def _title(self, page) -> str:
        return getattr(page, "title", "")

    def _rel(self, page) -> str:
        return getattr(page, "rel", "")

    def _path(self, page) -> Path | None:
        p = getattr(page, "path", None)
        return Path(p) if p else None

    def _raw_text(self, page) -> str:
        path = self._path(page)
        if path and path.is_file():
            return path.read_text(encoding="utf-8")
        return getattr(page, "raw", "")

    def _headings(self, page):
        return list(getattr(page, "headings", []) or [])

    def _breadcrumbs(self, page) -> list[str]:
        if self._rel(page) == "index.md":
            return ["docs", "home"]
        parts = self._rel(page).removesuffix(".md").split("/")
        crumbs = ["docs"]
        if len(parts) > 1:
            crumbs.extend(p.replace("-", " ") for p in parts[:-1])
        crumbs.append(self._title(page))
        return crumbs

    def _prev_next(self, page):
        if self.index and isinstance(page, IndexedPage):
            prev, nxt = self.index.prev_next(page.route)
            return (
                (prev.title, prev.route) if prev else None,
                (nxt.title, nxt.route) if nxt else None,
            )
        pid = self._route(page) or self._rel(page)
        for i, p in enumerate(self.pages):
            cur = self._route(p) or self._rel(p)
            if cur == pid:
                prev = self.pages[i - 1] if i > 0 else None
                nxt = self.pages[i + 1] if i + 1 < len(self.pages) else None
                return (
                    (self._title(prev), self._route(prev) or self._rel(prev))
                    if prev
                    else None,
                    (self._title(nxt), self._route(nxt) or self._rel(nxt))
                    if nxt
                    else None,
                )
        return None, None

    def _show(self) -> None:
        page = self.current
        if page is None:
            return
        try:
            meta = f"{self._rel(page)}" if self._rel(page) else "docs"
            crumbs = self._breadcrumbs(page)
            crumb_routes = self._breadcrumb_routes(page, crumbs)
            self.query_one("#dc-topbar").set_state(
                crumbs,
                actions="/ search  Ctrl+K palette  c copy  y link  e edit  ? help",
                theme=DEFAULT,
                meta=meta,
                crumb_routes=crumb_routes,
            )  # type: ignore[attr-defined]
        except AttributeError, NoMatches, TypeError, ValueError:
            try:
                from downcroc.cli.design.components.breadcrumb_bar import BreadcrumbBar

                crumbs = self._breadcrumbs(page)
                self.query_one("#dc-topbar").update(
                    BreadcrumbBar(
                        [
                            (c, "active" if i == len(crumbs) - 1 else "default")
                            for i, c in enumerate(crumbs)
                        ],
                        DEFAULT,
                    )
                )
            except NoMatches:
                pass
        self._render_content(page)
        self._render_toc(page)
        self._sync_nav(page)
        self._update_keybar()
        self.call_after_refresh(self._sync_toc_active)

    def _render_content(self, page) -> None:
        width = self._content_width()
        prev, nxt = self._prev_next(page)
        source = self._raw_text(page)
        doc = parse_document(source)
        try:
            from downcroc.cli.docs.md_render import render_page_sections

            sections = render_page_sections(
                doc,
                title=self._title(page) or doc.title,
                description=getattr(page, "description", "") or doc.description,
                breadcrumbs=self._breadcrumbs(page),
                prev_next=(prev, nxt),
                theme=DEFAULT,
                width=width,
            )
            self.shell.set_article_sections(
                sections, pager=(prev, nxt), content_width=width
            )
        except AttributeError, NoMatches, TypeError, ValueError:
            content = render_page_v2(
                doc,
                title=self._title(page) or doc.title,
                description=getattr(page, "description", "") or doc.description,
                breadcrumbs=self._breadcrumbs(page),
                prev_next=(prev, nxt),
                theme=DEFAULT,
                width=width,
            )
            self.shell.set_content(content)
        self.shell.scroll_article_home()

    def _content_width(self) -> int:
        width = self.size.width
        show_sidebar = width >= MEDIUM
        show_outline = width >= 118
        if show_sidebar and show_outline:
            width -= 28 + 26 + 6
        elif show_sidebar:
            width -= 28 + 4
        else:
            width -= 2
        return max(34, min(width, 92))

    def _render_toc(self, page) -> None:
        headings = self._headings(page)
        try:
            self.shell.set_toc(headings, DEFAULT)
        except AttributeError, NoMatches:
            try:
                toc = self.query_one("#dc-toc", OptionList)
            except NoMatches:
                return
            fill_toc(toc, headings)

    def _sync_toc_active(self) -> None:
        headings = self._headings(self.current) if self.current else []
        ratio = self.shell.article_scroll_ratio()
        active_slug = None
        if headings:
            ratios = self._heading_ratios(self.current)
            best = -1.0
            for h in headings:
                htext = h if isinstance(h, str) else getattr(h, "text", "")
                slug = str(
                    h if isinstance(h, str) else getattr(h, "slug", _slug(str(htext)))
                )
                r = ratios.get(slug, 0.0)
                if r <= ratio + 0.02 and r >= best:
                    best = r
                    active_slug = slug
            if active_slug is None and headings:
                h0 = headings[0]
                htext = h0 if isinstance(h0, str) else getattr(h0, "text", "")
                active_slug = str(
                    h0
                    if isinstance(h0, str)
                    else getattr(h0, "slug", _slug(str(htext)))
                )
        try:
            self.shell.set_toc_active(active_slug)
            return
        except AttributeError, NoMatches:
            pass
        try:
            toc = self.query_one("#dc-toc", OptionList)
        except NoMatches:
            return
        count = toc.option_count
        if count <= 0:
            return
        if active_slug:
            for i in range(count):
                opt = toc.get_option_at_index(i)
                if (
                    opt
                    and opt.id
                    and (
                        opt.id == active_slug
                        or _slug(str(opt.id)) == _slug(str(active_slug))
                    )
                ):
                    toc.highlighted = i
                    return
        idx = int(ratio * count)
        idx = max(0, min(count - 1, idx))
        for _ in range(count):
            opt = toc.get_option_at_index(idx)
            if opt and opt.id is not None:
                toc.highlighted = idx
                return
            idx = min(count - 1, idx + 1)

    def on_scroll(self, event) -> None:
        try:
            sender = event.control
        except AttributeError:
            return
        if getattr(sender, "id", "") == "dc-article":
            self._sync_toc_active()

    def _sync_nav(self, page) -> None:
        target = self._route(page) or self._rel(page)
        try:
            self.shell.set_sidebar(self.pages, active_route=target, theme=DEFAULT)
            return
        except AttributeError, NoMatches:
            pass
        try:
            nav = self.query_one("#dc-nav", OptionList)
        except NoMatches:
            return
        for i in range(nav.option_count):
            opt = nav.get_option_at_index(i)
            if opt and opt.id in {target, target + ".md", self._rel(page)}:
                nav.highlighted = i
                break

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option.id:
            return
        if event.option_list.id in {"dc-nav", "dc-nav-options"}:
            page = _find_by_id(self.pages, event.option.id)
            if page is not None:
                self._navigate(page)
        elif event.option_list.id == "dc-toc":
            self._scroll_to_heading(event.option.id)

    def on_primitive_action(self, event: PrimitiveAction) -> None:
        payload = getattr(getattr(event, "action", None), "payload", {}) or {}
        anchor = payload.get("anchor") or getattr(
            getattr(event, "action", None), "target", None
        )
        if not anchor:
            return
        try:
            sender = event.control
        except AttributeError:
            sender = None
        if isinstance(sender, StatefulTocWidget):
            self._scroll_to_heading(str(anchor))

    def _breadcrumb_routes(self, page, crumbs: list[str]) -> list[str | None]:
        routes: list[str | None] = [None] * len(crumbs)
        if not crumbs:
            return routes
        # "docs" -> home/index route
        routes[0] = self._route(self.pages[0]) if self.pages else ""
        # last crumb is current page
        routes[-1] = self._route(page)
        # try map intermediate section labels to first page in that section
        rel = self._rel(page).removesuffix(".md")
        parts = rel.split("/") if rel else []
        for i in range(1, max(len(crumbs) - 1, 1)):
            if i - 1 < len(parts) - 1:
                section = parts[i - 1]
                for p in self.pages:
                    prel = self._rel(p)
                    if prel.startswith(f"{section}/") or prel == f"{section}.md":
                        routes[i] = self._route(p)
                        break
        return routes

    def on_heading_copy_link(self, event: HeadingCopyLink) -> None:
        anchor = str(getattr(event, "anchor", "") or "").strip()
        if not anchor:
            return
        route = self._route(self.current) if self.current else ""
        base = self._page_link(self.current) if self.current else route
        if "#" in base:
            base = base.split("#", 1)[0]
        link = f"{base}#{anchor}" if base else f"#{anchor}"
        ok = clipboard.copy(link)
        self.notify(
            f"Copied heading link: {link}" if ok else "Clipboard unavailable",
            severity="information" if ok else "warning",
        )

    def on_breadcrumb_navigate(self, event: BreadcrumbNavigate) -> None:
        self._navigate_to_route(event.route)

    def on_topbar_action_activate(self, event: TopbarActionActivate) -> None:
        action = event.action
        if action == "dc-palette":
            self.action_palette()
        elif action == "help":
            self.action_help()
        elif action == "copy":
            self.action_copy()
        elif action == "copy_link":
            self.action_copy_link()

    def on_sidebar_navigate(self, event: SidebarNavigate) -> None:
        if event.route:
            page = _find_by_id(self.pages, event.route)
            if page is not None:
                self._navigate(page)

    def on_pager_navigate(self, event: PagerNavigate) -> None:
        if event.route:
            self._navigate_to_route(event.route)

    def _scroll_to_heading(self, heading_id: str) -> None:
        target = str(heading_id)
        headings = self._headings(self.current) if self.current else []
        known_slugs = {
            str(
                h
                if isinstance(h, str)
                else getattr(h, "slug", _slug(str(getattr(h, "text", ""))))
            )
            for h in headings
        }
        if target not in known_slugs:
            for h in headings:
                text = h if isinstance(h, str) else getattr(h, "text", "")
                slug = h if isinstance(h, str) else getattr(h, "slug", _slug(str(text)))
                if _slug(str(text)) == target or str(slug) == target:
                    target = str(slug) if not isinstance(h, str) else _slug(str(text))
                    break
        scrolled = False
        try:
            scrolled = bool(self.shell.scroll_to_anchor(target))
        except AttributeError, NoMatches, TypeError, ValueError:
            scrolled = False
        if not scrolled:
            ratios = self._heading_ratios(self.current)
            ratio = ratios.get(target)
            if ratio is None and ratios:
                idx = 0
                for i, h in enumerate(headings):
                    slug = h if isinstance(h, str) else getattr(h, "slug", "")
                    text = h if isinstance(h, str) else getattr(h, "text", "")
                    if str(slug) == heading_id or _slug(str(text)) == heading_id:
                        idx = i
                        break
                ratio = idx / max(len(headings), 1) if headings else 0.0
            if ratio is not None:
                self.shell.scroll_article_to_ratio(ratio)
        try:
            self.shell.set_toc_active(target)
        except AttributeError, NoMatches:
            pass
        self._sync_toc_active()

    def _heading_ratios(self, page) -> dict[str, float]:
        if page is None:
            return {}
        key = (self._route(page) or self._rel(page), self._content_width(), self.raw)
        cache = getattr(self, "_heading_ratio_cache", {})
        if cache.get("key") == key:
            return cache.get("ratios", {})
        headings = self._headings(page)
        ratios: dict[str, float] = {}
        if not headings:
            self._heading_ratio_cache = {"key": key, "ratios": ratios}
            return ratios
        try:
            from rich.console import Console

            source = self._raw_text(page)
            doc = parse_document(source)
            rendered = render_page_v2(
                doc,
                title=self._title(page) or doc.title,
                description=getattr(page, "description", "") or doc.description,
                breadcrumbs=self._breadcrumbs(page),
                prev_next=self._prev_next(page),
                theme=DEFAULT,
                width=self._content_width(),
            )
            c = Console(
                record=True,
                width=max(40, self._content_width() + 8),
                force_terminal=False,
                color_system=None,
            )
            c.print(rendered)
            text_out = c.export_text()
            lines = text_out.splitlines() or [""]
            total = max(len(lines), 1)
            pos = 0
            for h in headings:
                htext = h if isinstance(h, str) else getattr(h, "text", "")
                slug = (
                    h if isinstance(h, str) else getattr(h, "slug", _slug(str(htext)))
                )
                needle = str(htext).strip()
                found = None
                if needle:
                    for i in range(pos, len(lines)):
                        if needle in lines[i]:
                            found = i
                            break
                if found is None:
                    idx = headings.index(h) if h in headings else 0
                    found = int((idx / max(len(headings), 1)) * total)
                ratios[str(slug)] = max(0.0, min(1.0, found / total))
                pos = found + 1
        except AttributeError, OSError, RuntimeError, TypeError, ValueError:
            for i, h in enumerate(headings):
                htext = h if isinstance(h, str) else getattr(h, "text", "")
                slug = (
                    h if isinstance(h, str) else getattr(h, "slug", _slug(str(htext)))
                )
                ratios[str(slug)] = i / max(len(headings), 1)
        self._heading_ratio_cache = {"key": key, "ratios": ratios}
        return ratios

    def _navigate(self, page, *, push_history: bool = True) -> None:
        if push_history and self.current is not None:
            self._history.append(self._route(self.current) or self._rel(self.current))
        self.current = page
        self._heading_ratio_cache = {}
        self._show()

    def _navigate_to_route(self, route: str) -> None:
        page = _find_by_id(self.pages, route)
        if page is None and self.index:
            found = self.index.get(route)
            if found:
                page = found
        if page is not None:
            self._navigate(page)

    def action_menu(self) -> None:
        if self.size.width >= MEDIUM:
            try:
                self.query_one("#dc-nav-widget").focus()
            except NoMatches:
                try:
                    self.query_one("#dc-nav", OptionList).focus()
                except NoMatches:
                    pass
            return
        self._overlay_open = True
        self.shell.set_overlay(True)
        self.push_screen(NavScreen(self.pages), self._on_nav_modal)

    def _on_nav_modal(self, page) -> None:
        self.shell.set_overlay(False)
        self._overlay_open = False
        if page is not None:
            self._navigate(page)

    def action_palette(self) -> None:
        items = self._palette_items()
        self._overlay_open = True
        self.shell.set_overlay(True)
        self.push_screen(CommandPaletteScreen(items), self._on_palette)

    def _palette_items(self) -> list[PaletteItem]:
        # spec-driven command palette groups (shadcn Command parts mapping)
        from downcroc.cli.docs.ui_specs import command_groups

        items: list[PaletteItem] = []
        groups = command_groups(self.pages, headings_for_page=self._headings)
        for group in groups:
            for spec in group.items:
                items.append(
                    PaletteItem(
                        id=spec.id,
                        title=spec.title,
                        subtitle=spec.subtitle,
                        kind=spec.kind,
                        payload=spec.payload or spec.id,
                        group=group.label,
                    )
                )
        seen: set[tuple[str, str, str]] = set()
        out: list[PaletteItem] = []
        for item in items:
            key = (item.id, item.payload, item.kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _on_palette(self, item: PaletteItem | None) -> None:
        self.shell.set_overlay(False)
        self._overlay_open = False
        if item is None:
            return
        if item.kind == "page":
            self._navigate_to_route(item.payload)
        elif item.kind == "heading":
            route, _, anchor = item.payload.partition("#")
            self._navigate_to_route(route)
            self.call_after_refresh(lambda a=anchor: self._scroll_to_heading(a))
        elif item.kind == "action":
            self._run_action(item.payload)

    def _run_action(self, action_id: str) -> None:
        if action_id == "action:copy":
            self.action_copy()
        elif action_id == "action:copy-link":
            self.action_copy_link()
        elif action_id == "action:copy-heading-link":
            self.action_copy_heading_link()
        elif action_id == "action:open":
            self.action_open()
        elif action_id == "action:raw":
            self.action_raw()
        elif action_id == "action:edit":
            self.action_edit()
        elif action_id == "action:help":
            self.action_help()

    def action_close_overlay(self) -> None:
        if self._overlay_open:
            self._overlay_open = False
            self.shell.set_overlay(False)

    def _page_link(self, page) -> str:
        route = self._route(page) or self._rel(page).removesuffix(".md")
        return f"downcroc://docs/{route}" if route else "downcroc://docs"

    def action_copy(self) -> None:
        if self.current is None:
            return
        ok = clipboard.copy(self._raw_text(self.current))
        self.notify("Page markdown copied" if ok else "Clipboard unavailable")

    def action_copy_link(self) -> None:
        if self.current is None:
            return
        ok = clipboard.copy(self._page_link(self.current))
        self.notify("Page link copied" if ok else "Clipboard unavailable")

    def action_copy_heading_link(self) -> None:
        if self.current is None:
            return
        headings = self._headings(self.current)
        anchor = ""
        if headings:
            try:
                host = self.query_one("#dc-toc-host")
                tocw = host.query(StatefulTocWidget).first(StatefulTocWidget)
                anchor = str(tocw.active_anchor or "")
            except NoMatches:
                anchor = ""
            if not anchor:
                try:
                    toc = self.query_one("#dc-toc", OptionList)
                    idx = toc.highlighted
                    if idx is not None and 0 <= idx < len(headings):
                        h = headings[idx]
                        anchor = (
                            h
                            if isinstance(h, str)
                            else getattr(h, "slug", getattr(h, "text", ""))
                        )
                    else:
                        h0 = headings[0]
                        anchor = (
                            h0
                            if isinstance(h0, str)
                            else getattr(h0, "slug", getattr(h0, "text", ""))
                        )
                except NoMatches:
                    h0 = headings[0]
                    anchor = (
                        h0
                        if isinstance(h0, str)
                        else getattr(h0, "slug", getattr(h0, "text", ""))
                    )
        anchor_slug = _slug(str(anchor)) if anchor else ""
        base = self._page_link(self.current)
        link = f"{base}#{anchor_slug}" if anchor_slug else base
        ok = clipboard.copy(link)
        self.notify("Heading link copied" if ok else "Clipboard unavailable")

    def action_open(self) -> None:
        path = self._path(self.current) if self.current else None
        if path:
            webbrowser.open(path.resolve().as_uri())
            self.notify("Opened in browser")

    def action_raw(self) -> None:
        self.raw = not self.raw
        self.notify("Raw/source view" if self.raw else "Rendered view")
        self._show()

    def action_edit(self) -> None:
        path = self._path(self.current) if self.current else None
        if not path:
            self.notify("No file path available")
            return
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if not editor:
            self.notify("Set $EDITOR or $VISUAL to open files")
            return
        try:
            with self.suspend():
                subprocess.run([*shlex.split(editor), str(path)], check=False)
        except (OSError, ValueError, RuntimeError) as exc:
            self.notify(f"Editor failed: {exc}")
            return
        self.notify(f"Opened in {editor}")

    def action_prev_page(self) -> None:
        if self.current is None:
            return
        prev, _ = self._prev_next(self.current)
        if prev:
            self._navigate_to_route(prev[1])

    def action_next_page(self) -> None:
        if self.current is None:
            return
        _, nxt = self._prev_next(self.current)
        if nxt:
            self._navigate_to_route(nxt[1])

    def action_help(self) -> None:
        self._overlay_open = True
        self.shell.set_overlay(True)
        self.push_screen(HelpScreen(), self._on_help)

    def _on_help(self, _result=None) -> None:
        self.shell.set_overlay(False)
        self._overlay_open = False

    def action_cycle_theme(self) -> None:
        self.action_change_theme()

    def action_search(self) -> None:
        self.action_palette()


def _try_build_index(pages: list[model.Page]) -> DocIndex | None:
    if not pages:
        return None
    try:
        candidate = pages[0].path.parent
        for _ in range(8):
            if (candidate / "index.md").is_file():
                return build_index(candidate)
            if candidate.parent == candidate:
                break
            candidate = candidate.parent
    except (
        AttributeError,
        IndexError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return None
    return None


def _initial_page(pages, index):
    if index:
        home = index.get("index") or index.get("")
        if home:
            return home
    for p in pages or []:
        if getattr(p, "rel", "") == "index.md":
            return p
    return pages[0] if pages else None


def _find_by_id(pages, pid):
    for p in pages:
        route = getattr(p, "route", "") or getattr(p, "rel", "").removesuffix(".md")
        rel = getattr(p, "rel", "")
        if pid in {
            route,
            rel,
            rel.removesuffix(".md"),
            "" if route == "index" else route,
        }:
            return p
    return None


def _slug(text: str) -> str:
    import re

    s = str(text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"
