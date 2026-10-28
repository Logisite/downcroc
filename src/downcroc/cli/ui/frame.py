from __future__ import annotations

import shutil
import sys
from typing import Self

from downcroc.cli.ui import ansi

MIN_COLUMNS = 20
MAX_COLUMNS = 120
FALLBACK_ROWS = 24


def geometry(fallback: int = 100) -> tuple[int, int]:
    size = shutil.get_terminal_size((fallback, FALLBACK_ROWS))
    return max(1, size.columns), max(1, size.lines)


def columns(ui: object) -> int:
    live, _ = geometry(getattr(ui, "width", 100))
    if getattr(ui, "wide", False):
        return live
    return min(live, MAX_COLUMNS)


def rows(ui: object) -> int:
    _, live = geometry(getattr(ui, "width", 100))
    return live


class Frame:
    """A block of rows that redraws in place, independent of newline translation."""

    def __init__(self, ui: object, stream=None) -> None:
        self._ui = ui
        self._stream = stream or sys.stdout
        self._rows = 0
        self._at = 0
        self._claimed = 0

    def __enter__(self) -> Self:
        self._stream.write(ansi.hide_cursor())
        self._stream.flush()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.erase()
        self._stream.write(ansi.show_cursor())
        self._stream.flush()

    def draw(self, lines: list[str]) -> None:
        limit = max(1, columns(self._ui) - 1)
        fitted = [ansi.fit(line, limit) for line in lines]
        self.erase()
        self._reserve(len(fitted))
        self._stream.write("\r\n".join(fitted) + "\r\n")
        self._stream.flush()
        self._rows = len(fitted)
        self._at = self._rows

    def place(self, column: int, row: int = 0) -> None:
        if not self._rows:
            return
        row = max(0, min(row, self._rows - 1))
        out = ansi.move_up(self._rows - row) + "\r" + ansi.move_right(column)
        self._stream.write(out)
        self._stream.flush()
        self._at = row

    def erase(self) -> None:
        if not self._rows:
            return
        out = "\r"
        if self._at < self._rows:
            out += ansi.move_down(self._rows - self._at)
        out += (ansi.move_up(1) + ansi.clear_line()) * self._rows
        self._rows = 0
        self._at = 0
        self._stream.write(out)
        self._stream.flush()

    def _reserve(self, needed: int) -> None:
        extra = needed - self._claimed
        if extra <= 0:
            return
        out = "\r\n" * (extra + 1) + ansi.move_up(extra + 1)
        self._stream.write(out)
        self._stream.flush()
        self._claimed = needed
