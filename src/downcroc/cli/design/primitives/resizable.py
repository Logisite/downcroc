"""Resizable panel primitives (shadcn Resizable mapping, layout spec)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResizablePanel:
    id: str
    default_size: int = 1
    min_size: int | None = None
    max_size: int | None = None


@dataclass(frozen=True)
class ResizablePanelGroup:
    direction: str = "horizontal"
    panels: tuple[ResizablePanel, ...] = field(default_factory=tuple)
    with_handle: bool = True
