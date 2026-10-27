from __future__ import annotations

import sys

from downcroc.cli.errors import Cancelled
from downcroc.cli.ui import ansi
from downcroc.cli.ui.keys import (
    BACKSPACE,
    CTRL_C,
    CTRL_D,
    CTRL_U,
    CTRL_W,
    DELETE,
    END,
    ENTER,
    ESC,
    HOME,
    LEFT,
    RIGHT,
    SPACE,
    Keys,
)
from downcroc.cli.ui.session import Ui


def edit_line(
    ui: Ui,
    label: str,
    *,
    default: str | None = None,
    mask: bool = False,
    required: bool = True,
) -> str:
    suffix = ui.dim(f"  [{default}]") if default else ""
    print(f"{ui.accent('?')} {ui.bold(label)}{suffix}")
    buffer = ""
    cursor = 0
    error = ""
    with Keys() as keys:
        while True:
            _draw(ui, buffer, cursor, mask, error, default)
            key = keys.read()
            error = ""
            if key in (CTRL_C, CTRL_D, ESC):
                _cancel(ui)
                raise Cancelled()
            if key == ENTER:
                value = buffer or (default or "")
                if not value and required:
                    error = "a value is required"
                    continue
                _close()
                _answer(ui, value, mask)
                return value
            if key == BACKSPACE:
                if cursor:
                    buffer = buffer[: cursor - 1] + buffer[cursor:]
                    cursor -= 1
            elif key == DELETE:
                buffer = buffer[:cursor] + buffer[cursor + 1 :]
            elif key == LEFT:
                cursor = max(0, cursor - 1)
            elif key == RIGHT:
                cursor = min(len(buffer), cursor + 1)
            elif key == HOME:
                cursor = 0
            elif key == END:
                cursor = len(buffer)
            elif key == CTRL_U:
                buffer = ""
                cursor = 0
            elif key == CTRL_W:
                cursor = _drop_word(buffer, cursor)
                buffer = buffer[:cursor] + buffer[cursor:]
            elif key == SPACE:
                buffer = buffer[:cursor] + " " + buffer[cursor:]
                cursor += 1
            elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                buffer = buffer[:cursor] + key + buffer[cursor:]
                cursor += 1


def _drop_word(buffer: str, cursor: int) -> int:
    spot = cursor
    while spot and buffer[spot - 1] == " ":
        spot -= 1
    while spot and buffer[spot - 1] != " ":
        spot -= 1
    return spot


def _draw(
    ui: Ui,
    buffer: str,
    cursor: int,
    mask: bool,
    error: str,
    default: str | None,
) -> None:
    shown = "*" * len(buffer) if mask else buffer
    if not shown and default:
        view = ui.dim(default)
        width = len(default)
        position = 0
    else:
        room = max(10, ui.width - 10)
        start = max(0, cursor - room + 1) if len(shown) > room else 0
        text = shown[start : start + room]
        view = text
        width = len(text)
        position = cursor - start
    pointer = ui.accent(ui.glyph("pointer"))
    tail = ui.paint(f"  {error}", "bad") if error else ""
    sys.stdout.write(ansi.clear_line() + f"{pointer} {view}{tail}")
    back = max(0, width - position) + ansi.width(tail)
    if back:
        sys.stdout.write(f"\x1b[{back}D")
    sys.stdout.flush()


def _close() -> None:
    sys.stdout.write(ansi.clear_line())
    sys.stdout.flush()


def _answer(ui: Ui, value: str, mask: bool) -> None:
    pointer = ui.accent(ui.glyph("pointer"))
    if not value:
        print(f"{pointer} {ui.dim('empty')}")
        return
    shown = "*" * len(value) if mask else value
    print(f"{pointer} {ui.bold(shown)}")


def _cancel(ui: Ui) -> None:
    sys.stdout.write(ansi.clear_line())
    pointer = ui.accent(ui.glyph("pointer"))
    print(f"{pointer} {ui.dim('cancelled')}")
