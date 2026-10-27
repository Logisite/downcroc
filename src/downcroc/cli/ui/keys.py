from __future__ import annotations

import os
import sys
from typing import Self

from downcroc.cli.errors import Cancelled

ENTER = "enter"
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
HOME = "home"
END = "end"
BACKSPACE = "backspace"
DELETE = "delete"
TAB = "tab"
ESC = "esc"
SPACE = "space"
CTRL_C = "ctrl_c"
CTRL_D = "ctrl_d"
CTRL_U = "ctrl_u"
CTRL_W = "ctrl_w"

CSI_KEYS = {
    "A": UP,
    "B": DOWN,
    "C": RIGHT,
    "D": LEFT,
    "H": HOME,
    "F": END,
    "1~": HOME,
    "4~": END,
    "3~": DELETE,
    "5~": "page_up",
    "6~": "page_down",
}

CONTROL_KEYS = {
    "\x03": CTRL_C,
    "\x04": CTRL_D,
    "\x15": CTRL_U,
    "\x17": CTRL_W,
    "\x08": BACKSPACE,
    "\x7f": BACKSPACE,
    "\t": TAB,
    "\r": ENTER,
    "\n": ENTER,
    " ": SPACE,
}


class Unavailable(RuntimeError):
    """Raised when the terminal cannot provide raw key presses."""


class Keys:
    """Read single key presses from a terminal, arrows included."""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdin
        self._saved: object = None
        self._windows = os.name == "nt"
        try:
            self._fd = self._stream.fileno()
        except (AttributeError, OSError) as error:
            raise Unavailable("no terminal input") from error

    def __enter__(self) -> Self:
        if self._windows:
            return self
        import termios
        import tty

        try:
            self._saved = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        except (OSError, termios.error) as error:
            raise Unavailable("terminal does not support raw input") from error
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._windows or self._saved is None:
            return
        import termios

        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        self._saved = None

    def read(self) -> str:
        return self._read_windows() if self._windows else self._read_posix()

    def _read_windows(self) -> str:
        import msvcrt

        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            return {
                "H": UP,
                "P": DOWN,
                "K": LEFT,
                "M": RIGHT,
                "G": HOME,
                "O": END,
                "S": DELETE,
                "I": "page_up",
                "Q": "page_down",
            }.get(code, "")
        if char == "\x1b":
            return ESC
        return CONTROL_KEYS.get(char, char)

    def _read_posix(self) -> str:
        first = os.read(self._fd, 1)
        if not first:
            raise Cancelled()
        if first == b"\x1b":
            return self._escape()
        char = self._decode(first)
        return CONTROL_KEYS.get(char, char)

    def _escape(self) -> str:
        import select

        ready, _, _ = select.select([self._fd], [], [], 0.03)
        if not ready:
            return ESC
        rest = os.read(self._fd, 1)
        if rest == b"[":
            return self._csi()
        if rest == b"O":
            return self._csi()
        return ESC

    def _csi(self) -> str:
        sequence = ""
        while len(sequence) < 8:
            char = os.read(self._fd, 1)
            if not char:
                break
            sequence += char.decode("ascii", "ignore")
            if sequence and ("@" <= sequence[-1] <= "~"):
                break
        if sequence.endswith("~"):
            return CSI_KEYS.get(sequence, "")
        return CSI_KEYS.get(sequence[-1:] if sequence else "", "")

    def _decode(self, lead: bytes) -> str:
        if lead[0] < 0x80:
            return lead.decode("ascii", "ignore")
        need = 1
        if lead[0] >= 0xF0:
            need = 3
        elif lead[0] >= 0xE0:
            need = 2
        buffer = lead
        while len(buffer) < need + 1:
            chunk = os.read(self._fd, 1)
            if not chunk:
                break
            buffer += chunk
        return buffer.decode("utf-8", "ignore")
