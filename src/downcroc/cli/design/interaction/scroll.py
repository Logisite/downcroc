"""Textual-aligned scroll and anchor helpers (no custom physics)."""

from __future__ import annotations

from typing import Any


def scroll_to_widget(container: Any, widget: Any, *, animate: bool = False) -> None:
    """Scroll a Textual scroll container to make widget visible."""
    scroll_to = getattr(container, "scroll_to_widget", None)
    if callable(scroll_to):
        scroll_to(widget, animate=animate)
        return
    # Fallback: attempt scroll_to by region
    region = getattr(widget, "region", None)
    if region is not None and hasattr(container, "scroll_to_region"):
        container.scroll_to_region(region, animate=animate)


def scroll_to_y(container: Any, y: float, *, animate: bool = False) -> None:
    """Scroll a Textual scroll container to a vertical offset."""
    scroll_to = getattr(container, "scroll_to", None)
    if callable(scroll_to):
        scroll_to(y=y, animate=animate)
        return
    if hasattr(container, "scroll_y"):
        container.scroll_y = y
