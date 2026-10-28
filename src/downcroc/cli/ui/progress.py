from __future__ import annotations

import sys

from downcroc.cli.ui import ansi
from downcroc.cli.ui.frame import columns
from downcroc.cli.ui.session import Ui

BAR_WIDTH = 16
MIN_BAR_WIDTH = 8
CLEAR = "\x1b[2K\r"


def _bar(fraction: float | None, width: int, tick: int) -> str:
    if fraction is None:
        cells = ["-"] * width
        size = max(3, width // 4)
        start = tick % width
        for offset in range(size):
            cells[(start + offset) % width] = "#"
        return "[" + "".join(cells) + "]"
    filled = round(max(0.0, min(fraction, 1.0)) * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


class Progress:
    """Rewrite one terminal line instead of printing a line per update."""

    def __init__(self, ui: Ui, stream=None) -> None:
        self._ui = ui
        self._stream = stream or sys.stderr
        self._tty = self._stream.isatty() and not ui.json_mode
        self._last = ""
        self._wrote = False
        self._tick = 0

    def __call__(self, text: str, fraction: float | None = None) -> None:
        if text == self._last:
            return
        self._last = text
        self._tick += 1
        if not self._tty:
            if fraction in (0.0, 1.0):
                print(text, file=self._stream)
            return
        width = max(1, columns(self._ui) - 1)
        line = f"{_bar(fraction, self._bar_width(width), self._tick)} {text}"
        self._stream.write(CLEAR + ansi.fit(line, width))
        self._stream.flush()
        self._wrote = True

    def done(self) -> None:
        if self._tty and self._wrote:
            self._stream.write("\n")
            self._stream.flush()
            self._wrote = False

    def _bar_width(self, width: int) -> int:
        return BAR_WIDTH if width >= 60 else MIN_BAR_WIDTH
