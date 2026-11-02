"""Rounded cyan panel that separates input from output."""

from __future__ import annotations

from downcroc.cli.ui import ansi
from downcroc.cli.ui.frame import columns
from downcroc.cli.ui.session import Ui

UNICODE = {
    "tl": "\u2552",
    "tr": "\u2555",
    "bl": "\u2558",
    "br": "\u255b",
    "h": "\u2500",
    "v": "\u2551",
}

MIN_WIDTH = 24
MAX_WIDTH = 72
PAD = 2
GAP = 2
MARGIN = 3


def width_for(ui: Ui) -> int:
    return max(12, min(columns(ui) - MARGIN * 2, MAX_WIDTH))


def content_width(ui: Ui, width: int | None = None) -> int:
    return (width or width_for(ui)) - 2 - PAD * 2


def gap() -> None:
    for _ in range(GAP):
        print()


def frame(
    ui: Ui,
    title: str,
    lines: list[str],
    width: int | None = None,
) -> list[str]:
    glyphs = UNICODE
    width = width or width_for(ui)
    inner = width - 2
    content = inner - PAD * 2
    title = ansi.clip(title, max(1, inner - 8))
    head = inner - ansi.cells(title) - 4
    top = (
        f"{glyphs['tl']}{glyphs['h'] * 2} {title} "
        f"{glyphs['h'] * max(0, head)}{glyphs['tr']}"
    )
    edge = " " * MARGIN
    out = [edge + ui.paint(top, "accent"), edge + _row(ui, glyphs, "", content)]
    for line in lines:
        out.append(edge + _row(ui, glyphs, ansi.fit(line, content), content))
    out.append(edge + _row(ui, glyphs, "", content))
    out.append(
        edge + ui.paint(glyphs["bl"] + glyphs["h"] * inner + glyphs["br"], "accent")
    )
    return out


def _row(ui: Ui, glyphs: dict[str, str], text: str, content: int) -> str:
    body = " " * PAD + ansi.pad(text, content) + " " * PAD
    wall = ui.paint(glyphs["v"], "accent")
    return wall + body + wall
