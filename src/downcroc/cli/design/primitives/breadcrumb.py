"""Breadcrumb primitives for docs navigation (shadcn-mapped, render + widgets)."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Static

from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme


class Breadcrumb(Horizontal):
    """shadcn Breadcrumb root."""


class BreadcrumbList(Horizontal):
    """shadcn BreadcrumbList."""


class BreadcrumbItem(Static):
    """shadcn BreadcrumbItem."""

    def __init__(
        self,
        text: str = "",
        theme: Theme = DEFAULT,
        *,
        tone: str = "fg_muted",
        **kwargs,
    ):
        super().__init__(label(text, theme, tone=tone) if text else "", **kwargs)


class BreadcrumbLink(BreadcrumbItem):
    """shadcn BreadcrumbLink."""


class BreadcrumbPage(BreadcrumbItem):
    """shadcn BreadcrumbPage (current)."""

    def __init__(self, text: str = "", theme: Theme = DEFAULT, **kwargs):
        super().__init__(text, theme, tone="fg_primary", **kwargs)


class BreadcrumbSeparator(Static):
    """shadcn BreadcrumbSeparator."""

    def __init__(self, text: str = "›", theme: Theme = DEFAULT, **kwargs):
        super().__init__(label(f" {text} ", theme, tone="fg_faint"), **kwargs)


class BreadcrumbEllipsis(Static):
    """shadcn BreadcrumbEllipsis."""

    def __init__(self, theme: Theme = DEFAULT, **kwargs):
        super().__init__(label("…", theme, tone="fg_faint"), **kwargs)
