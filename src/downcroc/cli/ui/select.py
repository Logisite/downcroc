from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Self

from downcroc.cli.errors import Cancelled
from downcroc.cli.ui import ansi
from downcroc.cli.ui.keys import (
    BACKSPACE,
    CTRL_C,
    CTRL_D,
    DOWN,
    END,
    ENTER,
    ESC,
    HOME,
    SPACE,
    UP,
    Keys,
)
from downcroc.cli.ui.session import Ui

ROWS = 12


@dataclass(frozen=True)
class Choice:
    label: str
    value: object = None
    detail: str = ""
    badge: str = ""


class Screen:
    """Draw a block of lines, then redraw it in place."""

    def __init__(self, ui: Ui, stream=None) -> None:
        self._ui = ui
        self._stream = stream or sys.stdout
        self._rows = 0

    def __enter__(self) -> Self:
        self._stream.write(ansi.hide_cursor())
        self._stream.flush()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.erase()
        self._stream.write(ansi.show_cursor())
        self._stream.flush()

    def erase(self) -> None:
        if not self._rows:
            return
        out = ""
        for _ in range(self._rows):
            out += ansi.move_up(1) + ansi.clear_line()
        self._rows = 0
        self._stream.write(out)
        self._stream.flush()

    def draw(self, lines: list[str]) -> None:
        self.erase()
        self._stream.write("\n".join(lines) + "\n")
        self._stream.flush()
        self._rows = len(lines)


def _clip(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "~"


def _hint(ui: Ui, back: bool, multi: bool, filtering: bool) -> str:
    parts = ["up/down move", "enter select"]
    if multi:
        parts[1] = "space toggle"
        parts.append("enter done")
    if filtering:
        parts = ["type to filter", "enter apply", "esc clear"]
    else:
        parts.append("/ filter")
    if back:
        parts.append("q back")
    else:
        parts.append("esc cancel")
    keys = "   ".join(parts)
    return ui.dim(f"  {keys}")


def _rows(
    ui: Ui,
    choices: list[Choice],
    visible: list[int],
    cursor: int,
    checked: set[int] | None,
    filtering: bool,
    query: str,
    back: bool,
) -> list[str]:
    labels = [choices[index].label for index in visible]
    label_width = min(max((len(label) for label in labels), default=0), 30)
    width = max(20, ui.width - 4)
    lines: list[str] = []
    window = visible
    if len(visible) > ROWS:
        position = visible.index(cursor) if cursor in visible else 0
        start = max(0, min(position - ROWS // 2, len(visible) - ROWS))
        window = visible[start : start + ROWS]
        if start:
            lines.append(ui.dim(f"  {start} more above"))
        if start + ROWS < len(visible):
            lines.append(ui.dim(f"  {len(visible) - start - ROWS} more below"))
    for index in window:
        choice = choices[index]
        active = index == cursor
        pointer = ui.accent(ui.glyph("pointer")) if active else " "
        text = _clip(choice.label, max(10, width - 8))
        label = ui.bold(text) if active else text
        prefix = ""
        if checked is not None:
            mark = ui.glyph("checked" if index in checked else "unchecked")
            prefix = f"{mark} "
        detail = ""
        if choice.detail:
            room = max(8, width - label_width - len(prefix) - 6)
            detail = ui.dim("  " + _clip(choice.detail, room))
        lines.append(f"  {pointer} {prefix}{label:<{label_width}}{detail}".rstrip())
    if not visible:
        lines.append(ui.dim("  no match"))
    if filtering:
        marker = ui.glyph("search")
        lines.append(ui.accent(f"  {marker} {query}"))
    lines.append(_hint(ui, back, checked is not None, filtering))
    return lines


def select(
    ui: Ui,
    title: str,
    choices: list[Choice],
    *,
    default: int | None = None,
    back: bool = True,
    multi: bool = False,
    filterable: bool = True,
    shortcuts: dict[str, int] | None = None,
) -> list[int] | int | None:
    if not choices:
        return [] if multi else None
    cursor = default if default is not None and 0 <= default < len(choices) else 0
    checked: set[int] = set()
    query = ""
    filtering = False
    shortcuts = shortcuts or {}
    print(f"{ui.accent('?')} {ui.bold(title)}")
    with Screen(ui) as screen, Keys() as keys:
        while True:
            visible = [
                index
                for index, choice in enumerate(choices)
                if query.casefold() in f"{choice.label} {choice.detail}".casefold()
            ]
            if cursor not in visible:
                cursor = visible[0] if visible else -1
            screen.draw(
                _rows(
                    ui,
                    choices,
                    visible,
                    cursor,
                    checked if multi else None,
                    filtering,
                    query,
                    back,
                )
            )
            key = keys.read()
            if key in (CTRL_C, CTRL_D):
                raise Cancelled()
            if filtering:
                if key in (ENTER,):
                    filtering = False
                elif key == ESC:
                    query = ""
                    filtering = False
                elif key == BACKSPACE:
                    query = query[:-1]
                elif key in (UP, DOWN):
                    cursor = _move(cursor, visible, -1 if key == UP else 1)
                elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                    query += key
                continue
            if key in shortcuts:
                cursor = shortcuts[key]
                screen.erase()
                _finish(ui, choices, {cursor} if not multi else checked, multi)
                return [cursor] if multi else choices[cursor].value
            if key == ESC or key in {"q", "Q"}:
                screen.erase()
                print(ui.dim(f"{ui.glyph('pointer')} cancelled"))
                if not back:
                    raise Cancelled()
                return None
            if key in (UP, "k"):
                cursor = _move(cursor, visible, -1)
            elif key in (DOWN, "j"):
                cursor = _move(cursor, visible, 1)
            elif key == HOME or key in {"g", "G"}:
                cursor = visible[0] if visible else -1
            elif key == END:
                cursor = visible[-1] if visible else -1
            elif key == "page_up":
                cursor = _move(cursor, visible, -ROWS)
            elif key == "page_down":
                cursor = _move(cursor, visible, ROWS)
            elif key == "/" and filterable:
                filtering = True
            elif key == SPACE and multi:
                if cursor in checked:
                    checked.remove(cursor)
                else:
                    checked.add(cursor)
            elif key in (ENTER, SPACE) and cursor >= 0:
                screen.erase()
                _finish(
                    ui,
                    choices,
                    {cursor} if not multi else checked,
                    multi,
                )
                if multi:
                    return sorted(checked)
                return choices[cursor].value
            elif isinstance(key, str) and key.isdigit() and key != "0":
                spot = int(key) - 1
                if spot < len(visible):
                    cursor = visible[spot]


def _move(cursor: int, visible: list[int], step: int) -> int:
    if not visible:
        return -1
    if cursor not in visible:
        return visible[0]
    position = visible.index(cursor) + step
    return visible[max(0, min(position, len(visible) - 1))]


def _finish(
    ui: Ui,
    choices: list[Choice],
    checked: set[int],
    multi: bool,
) -> None:
    pointer = ui.accent(ui.glyph("pointer"))
    if multi:
        names = ", ".join(choices[index].label for index in sorted(checked))
        word = "selected" if checked else "nothing selected"
        print(f"{pointer} {ui.bold(word)}" + (ui.dim(f"  {names}") if names else ""))
        return
    index = next(iter(checked))
    print(f"{pointer} {ui.bold(choices[index].label)}")
