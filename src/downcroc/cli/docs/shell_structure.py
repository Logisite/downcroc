"""Shadcn-aligned structural widgets for docs shell DOM (TUI mapping)."""

from __future__ import annotations

from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static


class SidebarProvider(Container):
    """shadcn SidebarProvider"""


class Sidebar(Vertical):
    """shadcn Sidebar"""


class SidebarHeader(Static):
    """shadcn SidebarHeader"""


class SidebarContent(VerticalScroll):
    """shadcn SidebarContent"""


class SidebarFooter(Static):
    """shadcn SidebarFooter"""


class SidebarRail(Static):
    """shadcn SidebarRail"""


class SidebarGroup(Container):
    """shadcn SidebarGroup"""


class SidebarGroupLabel(Static):
    """shadcn SidebarGroupLabel"""


class SidebarGroupContent(Vertical):
    """shadcn SidebarGroupContent"""


class SidebarMenu(Vertical):
    """shadcn SidebarMenu"""


class SidebarMenuItem(Vertical):
    """shadcn SidebarMenuItem"""


class SidebarMenuButton(Static):
    """shadcn SidebarMenuButton"""

    can_focus = True


class SidebarMenuBadge(Static):
    """shadcn SidebarMenuBadge"""


class SidebarMenuAction(Static):
    """shadcn SidebarMenuAction"""

    can_focus = True


class SidebarMenuSub(Vertical):
    """shadcn SidebarMenuSub"""


class SidebarMenuSubItem(Vertical):
    """shadcn SidebarMenuSubItem"""


class SidebarMenuSubButton(Static):
    """shadcn SidebarMenuSubButton"""

    can_focus = True


class SidebarInset(Vertical):
    """shadcn SidebarInset (main content area wrapper)"""


class SidebarTrigger(Static):
    """shadcn SidebarTrigger"""

    can_focus = True


class Separator(Static):
    """shadcn Separator"""


class Topbar(Horizontal):
    """shadcn-style topbar/header container"""


class Header(Horizontal):
    """Inset/header region (trigger + separator + breadcrumb)"""


class Breadcrumb(Horizontal):
    """shadcn Breadcrumb"""


class BreadcrumbList(Horizontal):
    """shadcn BreadcrumbList"""


class BreadcrumbItem(Static):
    """shadcn BreadcrumbItem"""


class BreadcrumbLink(Static):
    """shadcn BreadcrumbLink"""


class BreadcrumbPage(Static):
    """shadcn BreadcrumbPage"""


class BreadcrumbSeparator(Static):
    """shadcn BreadcrumbSeparator"""


class BreadcrumbEllipsis(Static):
    """shadcn BreadcrumbEllipsis"""


class TopbarActions(Horizontal):
    """shadcn-style topbar actions container"""


class Content(VerticalScroll):
    """Article/content scroll container (maps to main content region)"""


class PageHeader(Vertical):
    """Page header region inside content"""


class DocContent(Vertical):
    """Docs content region (page header + body + pager)"""


class DocBody(Vertical):
    """Main document body region"""


class PageFooter(Vertical):
    """Page footer/pager region inside content"""


class Outline(Vertical):
    """TOC/outline rail"""


class OutlineHeader(Static):
    """Outline header"""


class OutlineContent(Vertical):
    """Outline content host"""


class Keybar(Static):
    """App keybar/footer"""
