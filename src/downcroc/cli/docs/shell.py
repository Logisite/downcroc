"""Textual shell widgets for the 5-zone docs experience (Phase 4)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rich.console import RenderableType
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from downcroc.cli.design.components.pager import Pager
from downcroc.cli.design.docs_ui.sidebar import fill_sidebar_options
from downcroc.cli.design.docs_ui.toc import StatefulTocWidget
from downcroc.cli.design.docs_ui.topbar import TopbarAction, render_topbar
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.nav import NavItem
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme
from downcroc.cli.docs.shell_structure import (
    Breadcrumb as BreadcrumbRoot,
)
from downcroc.cli.docs.shell_structure import (
    BreadcrumbItem,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
    Content,
    DocBody,
    Header,
    Keybar,
    Outline,
    OutlineContent,
    OutlineHeader,
    PageHeader,
    Separator,
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarInset,
    SidebarMenu,
    SidebarMenuAction,
    SidebarMenuBadge,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarMenuSub,
    SidebarMenuSubButton,
    SidebarMenuSubItem,
    SidebarRail,
    TopbarActions,
)
from downcroc.cli.docs.shell_structure import (
    PageFooter as ArticlePageFooter,
)
from downcroc.cli.docs.shell_structure import (
    SidebarTrigger as SidebarTriggerBase,
)
from downcroc.cli.docs.ui_specs import sidebar_groups

DOCS_SHELL_CSS = """
Screen {
    layout: vertical;
    background: #000000;
    color: #e6edf3;
    scrollbar-size: 1 1;
}
#dc-docs-root {
    height: 1fr;
    background: #000000;
    color: #e6edf3;
    scrollbar-size: 1 1;
}
#dc-topbar, TopBar, Header {
    dock: top;
    height: auto;
    min-height: 1;
    background: #000000;
    color: #f0f6fc;
    padding: 0 1;
    border-bottom: solid #30363d;
}
#dc-sidebar-trigger {
    width: 3;
    min-width: 3;
    color: #c9d1d9;
}
#dc-sidebar-separator {
    width: 3;
    color: #30363d;
}
#dc-breadcrumb {
    width: 1fr;
}
SidebarRail {
    dock: right;
    width: 1;
    color: #30363d;
    background: #000000;
}
SidebarFooter {
    dock: bottom;
    height: auto;
    color: #8b949e;
    padding: 1 0 0 0;
}
#dc-workspace {
    height: 1fr;
    background: #000000;
    scrollbar-size: 1 1;
}
#dc-sidebar, Sidebar {
    width: 28;
    min-width: 22;
    max-width: 32;
    border-right: solid #30363d;
    padding: 1 1 0 1;
    background: #000000;
    scrollbar-size: 1 1;
}
SidebarHeader {
    height: auto;
    padding: 0 0 1 0;
    color: #8b949e;
}
SidebarContent, #dc-nav-scroll, #dc-toc-host {
    height: 1fr;
    scrollbar-size: 1 1;
    scrollbar-gutter: stable;
    background: #000000;
}
#dc-article-wrap, SidebarInset {
    width: 1fr;
    height: 1fr;
    min-width: 36;
    background: #000000;
}
#dc-article, Content {
    width: 1fr;
    height: 1fr;
    padding: 1 3 2 3;
    background: #000000;
    color: #f0f6fc;
    scrollbar-gutter: stable;
    scrollbar-size: 1 1;
}
#dc-outline, Outline {
    width: 26;
    min-width: 20;
    max-width: 30;
    border-left: solid #30363d;
    padding: 1 1 0 1;
    background: #000000;
    scrollbar-size: 1 1;
}

#dc-topbar-actions, TopbarActions {
    width: auto;
    height: auto;
    min-width: 20;
    content-align: right middle;
}
Breadcrumb, BreadcrumbList {
    height: auto;
}
BreadcrumbItem, BreadcrumbPage, BreadcrumbSeparator, BreadcrumbLinkWidget, TopbarActionButton {
    width: auto;
    height: 1;
}
PageHeader, DocBody, PageFooter, DocContent {
    width: 1fr;
    height: auto;
    background: #000000;
    color: #f0f6fc;
}
HeadingAnchorActionWidget {
    height: auto;
    width: 1fr;
    margin-bottom: 1;
}
SidebarGroupLabelWidget {
    height: auto;
}
SidebarMenuItem, SidebarMenuSubItem {
    height: auto;
    width: 1fr;
}
SidebarMenuButtonWidget, SidebarMenuSubButtonWidget {
    width: 1fr;
}
SidebarMenuBadge, SidebarMenuAction, SidebarMenuActionWidget {
    width: auto;
    height: auto;
    content-align: right middle;
}

#dc-keybar, Keybar {
    dock: bottom;
    height: auto;
    min-height: 1;
    background: #000000;
    color: #c9d1d9;
    padding: 0 2;
    border-top: solid #30363d;
}
Static {
    background: transparent;
    color: #e6edf3;
}
OptionList {
    background: transparent;
    border: none;
    padding: 0;
    height: 1fr;
    scrollbar-size: 1 1;
    scrollbar-size-vertical: 1;
}
VerticalScroll {
    scrollbar-size: 1 1;
    scrollbar-size-vertical: 1;
    scrollbar-background: #000000;
    scrollbar-background-hover: #000000;
    scrollbar-background-active: #000000;
    scrollbar-color: #232330;
    scrollbar-color-hover: #343444;
    scrollbar-color-active: #4c45a1;
}
OptionList:focus {
    border: none;
}
OptionList > .option-list--option {
    padding: 0 1;
    color: #8b949e;
}
OptionList > .option-list--option-highlighted {
    background: #16132b;
    color: #c9d1d9;
    text-style: bold;
}
OptionList > .option-list--option-hover {
    background: #0f0f14;
    color: #c9d1d9;
}
OptionList > .option-list--separator {
    color: #232330;
}
.zone-title {
    padding: 0 0 1 0;
    color: #626c7a;
}
#dc-article-content {
    width: 1fr;
}
SidebarNavWidget, StatefulTocWidget {
    height: auto;
}
#dc-overlay-scrim {
    layer: overlay;
    dock: top;
    width: 1fr;
    height: 1fr;
    background: #000000 65%;
    display: none;
}
#dc-overlay-scrim.visible {
    display: block;
}
"""


@dataclass(frozen=True)
class NavEntry:
    route: str
    rel: str
    title: str
    section: str


def nav_entries(pages) -> list[NavEntry]:
    out: list[NavEntry] = []
    for page in pages:
        rel = getattr(page, "rel", "")
        route = getattr(page, "route", "") or rel.removesuffix(".md")
        if route == "index":
            route = ""
        title = getattr(page, "title", rel)
        section = rel.split("/", 1)[0] if "/" in rel else ""
        out.append(NavEntry(route=route or rel, rel=rel, title=title, section=section))
    return out


def fill_nav(widget: OptionList, pages, *, active_route: str = "") -> None:
    fill_sidebar_options(
        widget,
        sidebar_groups(pages, active_route=active_route),
        active_route=active_route,
    )


def fill_toc(widget: OptionList, headings) -> None:
    widget.clear_options()
    if not headings:
        widget.add_option(Option("No headings", id=None, disabled=True))
        return
    for h in headings:
        if isinstance(h, str):
            text, slug, level = h, _slug(h), 1
        else:
            text = getattr(h, "text", str(h))
            slug = getattr(h, "slug", "") or _slug(text)
            level = int(getattr(h, "level", 1) or 1)
        indent = "  " * max(level - 1, 0)
        widget.add_option(Option(f"{indent}{text}", id=slug or _slug(text)))


def _slug(text: str) -> str:
    s = str(text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def _safe_anchor_id(text: str | None) -> str:
    if not text:
        return "section"
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(text)).strip("-").lower()
    return s or "section"


class SidebarNavigate(Message):
    def __init__(self, route: str) -> None:
        super().__init__()
        self.route = route


class BreadcrumbNavigate(Message):
    def __init__(self, route: str) -> None:
        super().__init__()
        self.route = route


class TopbarActionActivate(Message):
    def __init__(self, action: str) -> None:
        super().__init__()
        self.action = action


class SidebarToggle(Message):
    """Toggle sidebar visibility."""


class SidebarTriggerWidget(SidebarTriggerBase):
    """Focusable/clickable sidebar trigger (hamburger)."""

    can_focus = True

    def _activate(self) -> None:
        self.post_message(SidebarToggle())

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class BreadcrumbLinkWidget(BreadcrumbItem):
    """Clickable breadcrumb item (shadcn BreadcrumbLink semantics)."""

    can_focus = True

    def __init__(self, text: str, route: str, theme: Theme) -> None:
        super().__init__()
        self._text = text
        self._route = route
        self._theme = theme

    def render(self):
        tone = "accent_strong" if self.has_focus else "fg_muted"
        return label(self._text, self._theme, tone=tone)

    def _activate(self) -> None:
        if self._route is not None:
            self.post_message(BreadcrumbNavigate(self._route))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class TopbarActionButton(Static):
    """Focusable/clickable topbar action (help/copy/link)."""

    can_focus = True
    DEFAULT_CSS = "TopbarActionButton { width: auto; height: 1; }"

    def __init__(self, action: str, text: str, theme: Theme) -> None:
        super().__init__()
        self.action = action
        self._text = text
        self._theme = theme

    def render(self):
        tone = "accent_strong" if self.has_focus else "fg_muted"
        return label(self._text, self._theme, tone=tone)

    def _activate(self) -> None:
        self.post_message(TopbarActionActivate(self.action))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class TopbarSearchButton(TopbarActionButton):
    """Dedicated topbar search control (opens command palette/search)."""

    def __init__(self, theme: Theme, *, text: str = "/ search") -> None:
        super().__init__("palette", text, theme)


class SidebarMenuButtonWidget(SidebarMenuButton):
    """Focusable/clickable sidebar menu button (shadcn SidebarMenuButton)."""

    DEFAULT_CSS = """
    SidebarMenuButtonWidget { height: auto; width: 1fr; }
    """

    def __init__(
        self,
        route: str,
        title: str,
        theme: Theme,
        *,
        active: bool = False,
        indent: int = 0,
    ) -> None:
        super().__init__()
        self.route = route
        self._title = title
        self._theme = theme
        self._active = active
        self._indent = indent
        self.can_focus = True

    def render(self):
        state = "active" if self._active else ("focus" if self.has_focus else "default")
        return NavItem(
            self._title,
            self._theme,
            active=self._active,
            indent=self._indent + 1,
            state=state,
        )

    def _activate(self) -> None:
        self.post_message(SidebarNavigate(self.route))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class SidebarMenuActionWidget(SidebarMenuAction):
    """Focusable menu action control (shadcn SidebarMenuAction)."""

    def __init__(self, action: str, text: str, theme: Theme) -> None:
        super().__init__()
        self.action = action
        self._text = text
        self._theme = theme
        self.can_focus = True

    def render(self):
        tone = "accent_strong" if self.has_focus else "fg_faint"
        return label(self._text, self._theme, tone=tone)

    def _activate(self) -> None:
        if self.action.startswith("action:") or self.action in {
            "palette",
            "help",
            "copy",
            "copy_link",
        }:
            self.post_message(
                TopbarActionActivate(
                    self.action.replace("action:", "")
                    if self.action in {"action:copy-link"}
                    else self.action
                )
            )
        else:
            self.post_message(SidebarNavigate(self.action))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class SidebarMenuSubButtonWidget(SidebarMenuSubButton):
    """Focusable submenu button (shadcn SidebarMenuSubButton)."""

    def __init__(
        self,
        route: str,
        title: str,
        theme: Theme,
        *,
        active: bool = False,
        indent: int = 2,
    ) -> None:
        super().__init__()
        self.route = route
        self._title = title
        self._theme = theme
        self._active = active
        self._indent = indent
        self.can_focus = True

    def render(self):
        state = "active" if self._active else ("focus" if self.has_focus else "default")
        return NavItem(
            self._title,
            self._theme,
            active=self._active,
            indent=self._indent + 1,
            state=state,
        )

    def _activate(self) -> None:
        self.post_message(SidebarNavigate(self.route))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class SidebarGroupLabelWidget(SidebarGroupLabel):
    """Clickable/collapsible group label (shadcn SidebarGroupLabel)."""

    can_focus = True

    def __init__(
        self,
        group_key: str,
        text: str,
        theme: Theme,
        *,
        open_state: bool,
        collapsible: bool,
    ) -> None:
        super().__init__()
        self.group_key = group_key
        self._text = text
        self._theme = theme
        self._open = open_state
        self._collapsible = collapsible
        self.can_focus = collapsible

    def render(self):
        prefix = "▾ " if (self._open or not self._collapsible) else "▸ "
        tone = "accent_strong" if (self.has_focus and self._collapsible) else "fg_faint"
        return label(prefix + self._text, self._theme, tone=tone)

    def _toggle(self) -> None:
        if self._collapsible:
            self.post_message(SidebarGroupToggle(self.group_key))

    def on_click(self, event: events.Click) -> None:
        self._toggle()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._toggle()
            event.stop()


class SidebarGroupToggle(Message):
    def __init__(self, group_key: str) -> None:
        super().__init__()
        self.group_key = group_key


class SidebarNavWidget(Vertical):
    """Composed sidebar navigation tree (shadcn SidebarGroup/Menu/Item/Button)."""

    can_focus = False
    DEFAULT_CSS = """
    SidebarNavWidget { height: auto; width: 1fr; }
    SidebarGroup { height: auto; width: 1fr; padding-bottom: 1; }
    SidebarGroupLabel, SidebarGroupLabelWidget { height: auto; color: #8b949e; }
    SidebarGroupContent, SidebarMenu, SidebarMenuItem { height: auto; width: 1fr; }
    SidebarMenuButtonWidget { height: auto; width: 1fr; }
    """

    def __init__(
        self,
        groups,
        theme: Theme = DEFAULT,
        *,
        active_route: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._groups = list(groups or [])
        self._theme = theme
        self._active_route = active_route
        self._open_state: dict[str, bool] = {}

    def _group_key(self, group) -> str:
        return str(getattr(group, "label", "group"))

    def set_groups(self, groups, *, active_route: str = "") -> None:
        self._groups = list(groups or [])
        self._active_route = active_route
        for g in self._groups:
            key = self._group_key(g)
            if key not in self._open_state:
                self._open_state[key] = bool(getattr(g, "open", True))
        self._rebuild()

    def on_mount(self) -> None:
        self._rebuild()

    def on_sidebar_group_toggle(self, event: SidebarGroupToggle) -> None:
        self._open_state[event.group_key] = not self._open_state.get(
            event.group_key, True
        )
        self._rebuild()
        event.stop()

    def _rebuild(self) -> None:
        try:
            self.remove_children()
        except AttributeError, NoMatches, RuntimeError:
            for child in list(getattr(self, "children", []) or []):
                try:
                    child.remove()
                except AttributeError, NoMatches, RuntimeError, ValueError:
                    pass

        group_nodes = []
        for group in self._groups:
            key = self._group_key(group)
            is_open = self._open_state.get(key, bool(getattr(group, "open", True)))
            menu_items = []
            if not (group.collapsible and not is_open):
                for item in group.items:
                    active = bool(getattr(item, "active", False)) or item.route in {
                        self._active_route,
                        self._active_route.removesuffix(".md"),
                    }
                    badge = getattr(item, "badge", "")
                    action = getattr(item, "action", "")
                    subitems = tuple(getattr(item, "children", ()) or ())
                    btn = SidebarMenuButtonWidget(
                        item.route,
                        item.title,
                        self._theme,
                        active=active,
                        indent=getattr(item, "indent", 0),
                    )
                    children = [btn]
                    if badge:
                        children.append(
                            SidebarMenuBadge(
                                label(str(badge), self._theme, tone="fg_faint")
                            )
                        )
                    if action:
                        children.append(
                            SidebarMenuActionWidget(action, "• action", self._theme)
                        )
                    if subitems:
                        sub_nodes = []
                        for sub in subitems:
                            sub_active = bool(
                                getattr(sub, "active", False)
                            ) or sub.route in {
                                self._active_route,
                                self._active_route.removesuffix(".md"),
                            }
                            sub_btn = SidebarMenuSubButtonWidget(
                                sub.route,
                                sub.title,
                                self._theme,
                                active=sub_active,
                                indent=max(getattr(sub, "indent", 1), 1),
                            )
                            sub_nodes.append(SidebarMenuSubItem(sub_btn))
                        children.append(SidebarMenuSub(*sub_nodes))
                    menu_items.append(SidebarMenuItem(*children))
            menu = SidebarMenu(*menu_items)
            group_nodes.append(
                SidebarGroup(
                    SidebarGroupLabelWidget(
                        key,
                        group.label,
                        self._theme,
                        open_state=is_open,
                        collapsible=bool(getattr(group, "collapsible", False)),
                    ),
                    SidebarGroupContent(menu),
                )
            )
        if group_nodes:
            self.mount(*group_nodes)
        else:
            self.mount(Static(label("No pages", self._theme, tone="fg_muted")))


class HeadingCopyLink(Message):
    def __init__(self, anchor: str) -> None:
        super().__init__()
        self.anchor = anchor


class HeadingAnchorActionWidget(Static):
    """Per-heading anchor/copy-link control (shadcn-style inline action)."""

    can_focus = True
    DEFAULT_CSS = "HeadingAnchorActionWidget { height: 1; width: auto; }"

    def __init__(self, anchor: str, theme: Theme) -> None:
        super().__init__()
        self.anchor = anchor
        self._theme = theme

    def render(self):
        tone = "accent_strong" if self.has_focus else "fg_faint"
        return label(f"  # {self.anchor}  ⎘ copy", self._theme, tone=tone)

    def _activate(self) -> None:
        self.post_message(HeadingCopyLink(self.anchor))

    def on_click(self, event: events.Click) -> None:
        self._activate()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._activate()
            event.stop()


class PagerNavigate(Message):
    def __init__(self, route: str) -> None:
        super().__init__()
        self.route = route


class PagerNavWidget(Widget):
    can_focus = True
    DEFAULT_CSS = "PagerNavWidget { height: auto; width: 1fr; }"

    def __init__(
        self,
        prev: tuple[str, str] | None,
        nxt: tuple[str, str] | None,
        theme: Theme = DEFAULT,
        *,
        width: int = 72,
    ) -> None:
        super().__init__()
        self._prev = prev
        self._nxt = nxt
        self._theme = theme
        self._width = width
        self._hover: str | None = None

    def render(self):
        return Pager(
            self._theme,
            prev_label=self._prev[0] if self._prev else "",
            prev_target=self._prev[1] if self._prev else "",
            next_label=self._nxt[0] if self._nxt else "",
            next_target=self._nxt[1] if self._nxt else "",
            width=self._width,
            prev_state="hover" if self._hover == "prev" and self._prev else "default",
            next_state="hover" if self._hover == "next" and self._nxt else "default",
        )

    def on_mouse_move(self, event: events.MouseMove) -> None:
        # rough split: left half = prev, right half = next
        w = max(self.size.width, 1)
        side = "prev" if event.x < (w // 2) else "next"
        if side != self._hover:
            self._hover = side
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover = None
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        w = max(self.size.width, 1)
        if event.x < (w // 2) and self._prev:
            self.post_message(PagerNavigate(self._prev[1]))
        elif event.x >= (w // 2) and self._nxt:
            self.post_message(PagerNavigate(self._nxt[1]))

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            if self._hover == "prev" and self._prev:
                self.post_message(PagerNavigate(self._prev[1]))
                event.stop()
            elif self._hover == "next" and self._nxt:
                self.post_message(PagerNavigate(self._nxt[1]))
                event.stop()
            elif self._prev:
                self.post_message(PagerNavigate(self._prev[1]))
                event.stop()
        elif event.key in {"left", "h"} and self._prev:
            self._hover = "prev"
            self.refresh()
            self.post_message(PagerNavigate(self._prev[1]))
            event.stop()
        elif event.key in {"right", "l"} and self._nxt:
            self._hover = "next"
            self.refresh()
            self.post_message(PagerNavigate(self._nxt[1]))
            event.stop()


class TopBar(Header):
    """Header region: SidebarTrigger + Separator + Breadcrumb/Topbar actions."""

    def compose(self) -> ComposeResult:
        yield SidebarTriggerWidget("≡", id="dc-sidebar-trigger")
        yield Separator("│", id="dc-sidebar-separator")
        with BreadcrumbRoot(id="dc-breadcrumb"):
            yield BreadcrumbList(id="dc-breadcrumb-list")
        yield TopbarActions(id="dc-topbar-actions")

    def _render_topbar(self, crumbs: list[str], actions: str, theme: Theme, meta: str):
        # legacy helper retained; set_state now mounts Breadcrumb* widgets
        action_specs = []
        if actions:
            for token in actions.split("  "):
                token = token.strip()
                if not token:
                    continue
                parts = token.split(" ", 1)
                hint, label_text = (
                    (parts + [""])[:2] if len(parts) == 2 else ("", token)
                )
                action_specs.append(
                    TopbarAction(
                        id=label_text or token, label=label_text or token, hint=hint
                    )
                )
        return render_topbar(crumbs, action_specs or None, theme=theme, meta=meta)

    def set_state(
        self,
        crumbs: list[str],
        actions: str = "",
        theme: Theme = DEFAULT,
        meta: str = "",
        *,
        crumb_routes: list[str | None] | None = None,
        action_buttons: list[tuple[str, str]] | None = None,
    ) -> None:
        try:
            blist = self.query_one("#dc-breadcrumb-list", BreadcrumbList)
        except NoMatches:
            return
        try:
            blist.remove_children()
        except AttributeError, NoMatches, RuntimeError:
            for child in list(getattr(blist, "children", []) or []):
                try:
                    child.remove()
                except AttributeError, NoMatches, RuntimeError, ValueError:
                    pass
        nodes = []
        last = len(crumbs) - 1
        crumb_routes = crumb_routes or [None] * len(crumbs)
        # Breadcrumb ellipsis only for very deep paths (shadcn-style)
        collapsed = len(crumbs) > 4
        if collapsed:
            display_indices = [0, 1, last]
        else:
            display_indices = list(range(len(crumbs)))
        for pos, i in enumerate(display_indices):
            if pos > 0:
                nodes.append(BreadcrumbSeparator(label(" › ", theme, tone="fg_faint")))
            if collapsed and pos == 2 and last > 2:
                nodes.append(BreadcrumbItem(label("…", theme, tone="fg_faint")))
                nodes.append(BreadcrumbSeparator(label(" › ", theme, tone="fg_faint")))
            crumb = crumbs[i]
            route = crumb_routes[i] if i < len(crumb_routes) else None
            is_last = i == last
            if route and not is_last:
                nodes.append(BreadcrumbLinkWidget(str(crumb), route, theme))
            elif is_last:
                nodes.append(
                    BreadcrumbPage(label(str(crumb), theme, tone="fg_primary"))
                )
            else:
                nodes.append(BreadcrumbItem(label(str(crumb), theme, tone="fg_muted")))
        if meta:
            nodes.append(BreadcrumbSeparator(label(" · ", theme, tone="fg_faint")))
            nodes.append(BreadcrumbItem(label(str(meta), theme, tone="fg_faint")))
        if nodes:
            blist.mount(*nodes)

        action_buttons = action_buttons or [
            ("palette", "/ search"),
            ("help", "? help"),
            ("copy", "c copy"),
            ("copy_link", "y link"),
        ]
        try:
            actions_host = self.query_one("#dc-topbar-actions", TopbarActions)
        except NoMatches:
            actions_host = None
        if actions_host is not None:
            try:
                actions_host.remove_children()
            except AttributeError, NoMatches, RuntimeError:
                for child in list(getattr(actions_host, "children", []) or []):
                    try:
                        child.remove()
                    except AttributeError, NoMatches, RuntimeError, ValueError:
                        pass
            action_nodes = []
            for i, (aid, text_label) in enumerate(action_buttons):
                if i:
                    action_nodes.append(Separator(label("  ", theme, tone="fg_faint")))
                if aid == "palette":
                    action_nodes.append(TopbarSearchButton(theme, text=text_label))
                else:
                    action_nodes.append(TopbarActionButton(aid, text_label, theme))
            if action_nodes:
                actions_host.mount(*action_nodes)

    def set_breadcrumbs(
        self,
        crumbs: list[str],
        theme: Theme = DEFAULT,
        *,
        meta: str = "",
        actions: list[tuple[str, str]] | None = None,
    ) -> None:
        action_str = "  ".join(a for a, _ in (actions or []))
        self.set_state(crumbs, action_str, theme, meta=meta)


class DocsShell(Vertical):
    """5-zone shell: topbar, rail, article, outline, keybar."""

    def __init__(self, *children, id: str | None = "dc-docs-root", **kwargs) -> None:
        super().__init__(*children, id=id, **kwargs)
        self._anchor_ids: list[tuple[str | None, str]] = []
        self._section_mount_seq = 0

    def compose(self) -> ComposeResult:
        yield TopBar(id="dc-topbar")
        with Horizontal(id="dc-workspace"):
            with Sidebar(id="dc-sidebar"):
                yield SidebarHeader(
                    label("Navigation", DEFAULT, tone="fg_muted"),
                    id="dc-sidebar-header",
                )
                yield SidebarContent(
                    SidebarNavWidget([], DEFAULT, id="dc-nav-widget"),
                    id="dc-nav-scroll",
                )
                yield SidebarFooter(
                    label("downcroc docs", DEFAULT, tone="fg_faint"),
                    id="dc-sidebar-footer",
                )
                yield SidebarRail("│", id="dc-sidebar-rail")
            with SidebarInset(id="dc-article-wrap"):
                yield Content(id="dc-article")
            with Outline(id="dc-outline"):
                yield OutlineHeader(
                    SectionHeader("On this page", DEFAULT), id="dc-outline-title"
                )
                yield OutlineContent(id="dc-toc-host")
        yield Keybar("", id="dc-keybar")
        yield Static("", id="dc-overlay-scrim")

    def set_keybar(self, hints: list[tuple[str, str]], theme: Theme = DEFAULT) -> None:
        try:
            self.query_one("#dc-keybar").update(keybar(hints, theme))
        except NoMatches:
            pass

    def set_content(self, renderable: RenderableType) -> None:
        self.set_article_sections([(None, renderable)])

    def set_article_sections(
        self,
        sections: list[tuple[str | None, RenderableType]],
        *,
        pager: tuple[tuple[str, str] | None, tuple[str, str] | None] | None = None,
        content_width: int = 72,
    ) -> None:
        try:
            scroller = self.query_one("#dc-article", Content)
        except NoMatches:
            return
        try:
            scroller.remove_children()
        except AttributeError, NoMatches, RuntimeError:
            for child in list(getattr(scroller, "children", []) or []):
                try:
                    child.remove()
                except AttributeError, NoMatches, RuntimeError, ValueError:
                    pass
        self._anchor_ids = []
        mount_seq = getattr(self, "_section_mount_seq", 0) + 1
        self._section_mount_seq = mount_seq

        header_widgets = []
        body_widgets = []
        footer_widgets = []
        for idx, (anchor, renderable) in enumerate(sections):
            safe = _safe_anchor_id(anchor) if anchor else f"section-{idx}"
            if anchor == "__top__":
                safe = "anchor-top"
            elif anchor == "__pager__":
                safe = "anchor-pager"
            wid = f"sec-{mount_seq}-{idx}-{safe}"
            self._anchor_ids.append((anchor, wid))
            if anchor == "__pager__" and pager is not None:
                footer_widgets.append(
                    ArticlePageFooter(
                        PagerNavWidget(
                            pager[0],
                            pager[1],
                            DEFAULT,
                            width=min(max(content_width, 40), 92),
                        ),
                    )
                )
            elif anchor == "__top__":
                header_widgets.append(PageHeader(Static(renderable, id=wid)))
            else:
                body_widgets.append(Static(renderable, id=wid))

        if not header_widgets and not body_widgets and not footer_widgets:
            return

        containers = []
        if header_widgets:
            containers.extend(header_widgets)
        if body_widgets:
            # insert per-heading copy-link controls for anchored sections
            enriched = []
            for w in body_widgets:
                enriched.append(w)
                wid = getattr(w, "id", "") or ""
                # sec-{mount}-{idx}-{safe} ; recover anchor from stored map
                anchor = None
                for a, awid in self._anchor_ids:
                    if awid == wid and a not in (None, "__top__", "__pager__"):
                        anchor = a
                        break
                if anchor:
                    enriched.append(HeadingAnchorActionWidget(anchor, DEFAULT))
            containers.append(DocBody(*enriched))
        elif not header_widgets and footer_widgets:
            containers.append(DocBody())
        if footer_widgets:
            containers.extend(footer_widgets)
        scroller.mount(*containers)

    def scroll_article_home(self) -> None:
        try:
            self.query_one("#dc-article", Content).scroll_home(animate=False)
        except NoMatches:
            pass

    def scroll_to_anchor(self, anchor: str | None) -> bool:
        if not anchor:
            self.scroll_article_home()
            return True
        try:
            scroller = self.query_one("#dc-article", Content)
        except NoMatches:
            return False
        target_id = None
        for a, wid in getattr(self, "_anchor_ids", []):
            if a == anchor or (a and _safe_anchor_id(a) == _safe_anchor_id(anchor)):
                target_id = wid
                break
        if target_id is None and anchor in {"top", "__top__"}:
            self.scroll_article_home()
            return True
        if target_id is None:
            return False
        try:
            widget = scroller.query_one(f"#{target_id}")
            scroller.scroll_to_widget(widget, animate=False, top=True)
            return True
        except NoMatches:
            return False

    def scroll_article_to_ratio(self, ratio: float) -> None:
        try:
            scroller = self.query_one("#dc-article", Content)
            max_y = max(getattr(scroller, "max_scroll_y", 0), 0)
            scroller.scroll_to(y=int(max(0.0, min(1.0, ratio)) * max_y), animate=False)
        except NoMatches:
            pass

    def article_scroll_ratio(self) -> float:
        try:
            scroller = self.query_one("#dc-article", Content)
            max_y = max(getattr(scroller, "max_scroll_y", 0), 0)
            if max_y <= 0:
                return 0.0
            y = float(getattr(scroller, "scroll_y", 0) or 0.0)
            return max(0.0, min(1.0, y / max_y))
        except NoMatches:
            return 0.0

    def set_overlay(self, visible: bool) -> None:
        try:
            scrim = self.query_one("#dc-overlay-scrim", Static)
            scrim.set_class(visible, "visible")
        except NoMatches:
            pass

    def set_toc(
        self, headings, theme: Theme = DEFAULT, *, active_anchor: str | None = None
    ) -> None:
        try:
            host = self.query_one("#dc-toc-host")
        except NoMatches:
            return
        items = []
        for h in headings or []:
            if isinstance(h, str):
                text, slug, level = h, _slug(h), 1
            else:
                text = getattr(h, "text", str(h))
                slug = getattr(h, "slug", "") or _slug(text)
                level = int(getattr(h, "level", 1) or 1)
            items.append((text, {"anchor": slug, "level": level}))
        try:
            toc = host.query(StatefulTocWidget).first(StatefulTocWidget)
            toc.set_items(items, active_anchor=active_anchor)
            return
        except NoMatches:
            pass
        host.mount(StatefulTocWidget(items, theme, active_anchor=active_anchor))

    def set_toc_active(self, anchor: str | None) -> None:
        try:
            host = self.query_one("#dc-toc-host")
            toc = host.query(StatefulTocWidget).first(StatefulTocWidget)
            toc.set_active_anchor(anchor)
        except NoMatches:
            pass

    def set_sidebar(
        self, pages, *, active_route: str = "", theme: Theme = DEFAULT
    ) -> None:
        try:
            nav = self.query_one("#dc-nav-widget", SidebarNavWidget)
        except NoMatches:
            return
        nav.set_groups(
            sidebar_groups(pages, active_route=active_route), active_route=active_route
        )
