from __future__ import annotations

from dataclasses import dataclass

from downcroc.cli.errors import Cancelled
from downcroc.cli.ui import ansi
from downcroc.cli.ui.frame import Frame, columns, rows
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
MIN_ROWS = 3
LABEL_MAX = 30
DETAIL_FROM = 60
DROP_ORDER = (
    "/ filter",
    "enter apply",
    "up/down move",
    "enter select",
    "space toggle",
    "enter done",
    "q back",
    "esc cancel",
)


@dataclass(frozen=True)
class Choice:
    label: str
    value: object = None
    detail: str = ""
    badge: str = ""


def _window(ui: Ui) -> int:
    available = rows(ui) - 5
    return max(MIN_ROWS, min(ROWS, available))


def _hint(ui: Ui, back: bool, multi: bool, filtering: bool, limit: int) -> str:
    if filtering:
        parts = ["type to filter", "enter apply", "esc clear"]
    else:
        parts = ["up/down move", "space toggle" if multi else "enter select"]
        if multi:
            parts.append("enter done")
        parts.append("/ filter")
    parts.append("q back" if back else "esc cancel")
    for drop in DROP_ORDER:
        if len(parts) <= 1:
            break
        if ansi.cells("   ".join(parts)) + 2 <= limit:
            break
        if drop in parts:
            parts.remove(drop)
    return ui.dim(ansi.fit("  " + "   ".join(parts), limit))


def _row(
    ui: Ui,
    choice: Choice,
    active: bool,
    checked: bool | None,
    label_width: int,
    limit: int,
) -> str:
    pointer = ui.accent(ui.glyph("pointer")) if active else " "
    label = ansi.clip(choice.label, max(4, label_width))
    if active:
        label = ui.bold(label)
    prefix = ""
    if checked is not None:
        prefix = f"{ui.glyph('checked' if checked else 'unchecked')} "
    badge = ""
    if choice.badge and limit >= DETAIL_FROM:
        tone = "warn" if "paused" in choice.badge else "muted"
        badge = ui.paint(
            "  " + ansi.clip(choice.badge, max(8, label_width)),
            tone,
        )
    detail = ""
    if choice.detail and limit >= DETAIL_FROM:
        room = max(
            8,
            limit - label_width - ansi.cells(prefix) - ansi.cells(badge) - 6,
        )
        detail = ui.dim("  " + ansi.clip(choice.detail, room))
    label = ansi.pad(label, label_width)
    return ansi.fit(
        f"  {pointer} {prefix}{label}{badge}{detail}".rstrip(),
        limit,
    )


def _lines(
    ui: Ui,
    choices: list[Choice],
    visible: list[int],
    cursor: int,
    checked: set[int] | None,
    filtering: bool,
    query: str,
    back: bool,
    limit: int,
    window: int,
) -> list[str]:
    labels = [choices[index].label for index in visible]
    widest = max((ansi.cells(label) for label in labels), default=0)
    label_width = min(widest, LABEL_MAX, max(4, limit - 12))
    lines: list[str] = []
    shown = visible
    if len(visible) > window:
        position = visible.index(cursor) if cursor in visible else 0
        start = max(0, min(position - window // 2, len(visible) - window))
        shown = visible[start : start + window]
        if start:
            lines.append(ui.dim(ansi.fit(f"  {start} more above", limit)))
        if start + window < len(visible):
            left = len(visible) - start - window
            lines.append(ui.dim(ansi.fit(f"  {left} more below", limit)))
    for index in shown:
        mark = None if checked is None else index in checked
        lines.append(
            _row(ui, choices[index], index == cursor, mark, label_width, limit)
        )
    if not visible:
        lines.append(ui.dim(ansi.fit("  no match", limit)))
    if filtering:
        marker = ui.glyph("search")
        lines.append(ui.accent(ansi.fit(f"  {marker} {query}", limit)))
    lines.append(_hint(ui, back, checked is not None, filtering, limit))
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
    limit = max(1, columns(ui) - 1)
    print(ansi.fit(f"{ui.accent('?')} {ui.bold(title)}", limit))
    final: set[int] | None = None
    result: list[int] | int | None = None
    cancelled = False
    with Frame(ui) as screen, Keys() as keys:
        while True:
            limit = max(1, columns(ui) - 1)
            window = _window(ui)
            visible = [
                index
                for index, choice in enumerate(choices)
                if query.casefold() in f"{choice.label} {choice.detail}".casefold()
            ]
            if cursor not in visible:
                cursor = visible[0] if visible else -1
            screen.draw(
                _lines(
                    ui,
                    choices,
                    visible,
                    cursor,
                    checked if multi else None,
                    filtering,
                    query,
                    back,
                    limit,
                    window,
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
                final = {cursor}
                result = [cursor] if multi else choices[cursor].value
                break
            if key == ESC or key in {"q", "Q"}:
                cancelled = True
                break
            if key in (UP, "k"):
                cursor = _move(cursor, visible, -1)
            elif key in (DOWN, "j"):
                cursor = _move(cursor, visible, 1)
            elif key == HOME or key in {"g", "G"}:
                cursor = visible[0] if visible else -1
            elif key == END:
                cursor = visible[-1] if visible else -1
            elif key == "page_up":
                cursor = _move(cursor, visible, -window)
            elif key == "page_down":
                cursor = _move(cursor, visible, window)
            elif key == "/" and filterable:
                filtering = True
            elif key == SPACE and multi:
                if cursor in checked:
                    checked.remove(cursor)
                else:
                    checked.add(cursor)
            elif key in (ENTER, SPACE) and cursor >= 0:
                final = {cursor} if not multi else set(checked)
                result = sorted(checked) if multi else choices[cursor].value
                break
            elif isinstance(key, str) and key.isdigit() and key != "0":
                spot = int(key) - 1
                if spot < len(visible):
                    cursor = visible[spot]
    limit = max(1, columns(ui) - 1)
    if cancelled:
        print(ui.dim(f"{ui.glyph('pointer')} cancelled"))
        if not back:
            raise Cancelled()
        return None
    if final is not None:
        _finish(ui, choices, final, multi, limit)
    return result


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
    limit: int,
) -> None:
    pointer = ui.accent(ui.glyph("pointer"))
    if multi:
        names = ", ".join(choices[index].label for index in sorted(checked))
        word = "selected" if checked else "nothing selected"
        line = f"{pointer} {ui.bold(word)}" + (ui.dim(f"  {names}") if names else "")
        print(ansi.fit(line, limit))
        return
    index = next(iter(checked))
    print(ansi.fit(f"{pointer} {ui.bold(choices[index].label)}", limit))
