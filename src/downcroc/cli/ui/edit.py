from __future__ import annotations

from downcroc.cli.errors import Cancelled
from downcroc.cli.ui import ansi
from downcroc.cli.ui.frame import Frame, columns
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
    limit = max(1, columns(ui) - 1)
    print(ansi.fit(f"{ui.accent('?')} {ui.bold(label)}{suffix}", limit))
    buffer = ""
    cursor = 0
    error = ""
    drawn: tuple[str, int, str] | None = None
    value = ""
    cancelled = False
    with Keys() as keys, Frame(ui) as frame:
        while True:
            state = (buffer, cursor, error)
            if state != drawn:
                text, column = _render(ui, buffer, cursor, mask, error, default)
                frame.draw([text])
                frame.place(column)
                drawn = state
            key = keys.read()
            error = ""
            if key in (CTRL_C, CTRL_D, ESC):
                cancelled = True
                break
            if key == ENTER:
                value = buffer or (default or "")
                if not value and required:
                    error = "a value is required"
                    continue
                break
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
    if cancelled:
        _cancel(ui)
        raise Cancelled()
    _answer(ui, value, mask)
    return value


def _drop_word(buffer: str, cursor: int) -> int:
    spot = cursor
    while spot and buffer[spot - 1] == " ":
        spot -= 1
    while spot and buffer[spot - 1] != " ":
        spot -= 1
    return spot


def _render(
    ui: Ui,
    buffer: str,
    cursor: int,
    mask: bool,
    error: str,
    default: str | None,
) -> tuple[str, int]:
    limit = max(1, columns(ui) - 1)
    shown = "*" * len(buffer) if mask else buffer
    if not shown and default:
        view = ui.dim(default)
        position = 0
        source = default
    else:
        room = max(4, limit - 4)
        start = max(0, cursor - room + 1) if len(shown) > room else 0
        text = shown[start : start + room]
        view = text
        position = cursor - start
        source = text
    pointer = ui.accent(ui.glyph("pointer"))
    tail = ui.paint(f"  {error}", "bad") if error else ""
    line = ansi.fit(f"{pointer} {view}{tail}", limit)
    column = ansi.cells(pointer) + 1 + ansi.cells(source[:position])
    return line, min(column, ansi.cells(line))


def _answer(ui: Ui, value: str, mask: bool) -> None:
    pointer = ui.accent(ui.glyph("pointer"))
    if not value:
        print(f"{pointer} {ui.dim('empty')}")
        return
    shown = "*" * len(value) if mask else value
    print(f"{pointer} {ui.bold(shown)}")


def _cancel(ui: Ui) -> None:
    pointer = ui.accent(ui.glyph("pointer"))
    print(f"{pointer} {ui.dim('cancelled')}")
