"""Sidebar components mapped to shadcn Sidebar parts (TUI)."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Group
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from downcroc.cli.design.primitives.collapsible import Collapsible
from downcroc.cli.design.primitives.nav import NavItem
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme


@dataclass(frozen=True)
class SidebarMenuItem:
    title: str
    route: str
    icon: str = ""
    active: bool = False
    indent: int = 0
    badge: str = ""
    action: str = ""
    children: tuple[SidebarMenuItem, ...] = ()


@dataclass(frozen=True)
class SidebarGroupSpec:
    label: str
    items: tuple[SidebarMenuItem, ...] = field(default_factory=tuple)
    collapsible: bool = False
    open: bool = True


class SidebarHeader(Static):
    def __init__(self, title: str = "Documentation", theme: Theme = DEFAULT, **kwargs):
        super().__init__(label(title, theme, tone="fg_muted"), **kwargs)


class SidebarContent(Vertical):
    pass


class SidebarGroup(Vertical):
    def __init__(self, spec: SidebarGroupSpec, theme: Theme = DEFAULT, **kwargs):
        super().__init__(**kwargs)
        self.spec = spec
        self.theme = theme

    def compose(self):
        if self.spec.collapsible:
            content = Group(
                *[
                    NavItem(
                        item.title,
                        self.theme,
                        icon=item.icon,
                        active=item.active,
                        indent=item.indent,
                        badge_text=item.badge,
                    )
                    for item in self.spec.items
                ]
            )
            yield Static(
                Collapsible(
                    self.spec.label,
                    content if self.spec.open else None,
                    open=self.spec.open,
                    theme=self.theme,
                )
            )
        else:
            yield Static(label(self.spec.label, self.theme, tone="fg_faint"))
            for item in self.spec.items:
                yield Static(
                    NavItem(
                        item.title,
                        self.theme,
                        icon=item.icon,
                        active=item.active,
                        indent=item.indent,
                        badge_text=item.badge,
                    )
                )


class SidebarFooter(Static):
    def __init__(self, text: str = "", theme: Theme = DEFAULT, **kwargs):
        super().__init__(label(text, theme, tone="fg_faint") if text else "", **kwargs)


def fill_sidebar_options(
    widget: OptionList, groups: list[SidebarGroupSpec], *, active_route: str = ""
) -> None:
    widget.clear_options()
    for group in groups:
        prefix = "▾" if (group.open or not group.collapsible) else "▸"
        widget.add_option(Option(f"{prefix} {group.label}", id=None, disabled=True))
        if group.collapsible and not group.open:
            continue
        for item in group.items:
            indent = "    " + ("  " * max(item.indent, 0))
            marker = "• " if item.active else ""
            widget.add_option(Option(f"{indent}{marker}{item.title}", id=item.route))
    for i in range(widget.option_count):
        opt = widget.get_option_at_index(i)
        if opt and opt.id and opt.id in {active_route, active_route + ".md"}:
            widget.highlighted = i
            break
