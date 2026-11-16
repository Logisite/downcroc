"""Pager/footer navigation component mapping."""

from __future__ import annotations

from dataclasses import dataclass

from downcroc.cli.design.components.pager import Pager
from downcroc.cli.design.theme import DEFAULT, Theme


@dataclass(frozen=True)
class PagerLink:
    label: str = ""
    target: str = ""


def render_doc_pager(
    prev: PagerLink | None,
    nxt: PagerLink | None,
    *,
    theme: Theme = DEFAULT,
    width: int = 72,
) -> Pager:
    return Pager(
        theme,
        prev_label=prev.label if prev else "",
        prev_target=prev.target if prev else "",
        next_label=nxt.label if nxt else "",
        next_target=nxt.target if nxt else "",
        width=width,
    )
