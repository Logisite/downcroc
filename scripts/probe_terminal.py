"""Render what a child process actually draws on a terminal.

The probe does not assert. It feeds a pty and paints the bytes the app emits
into a small screen buffer, so a human can read the keystrokes and the screen
that came back.
"""

from __future__ import annotations

import codecs
import fcntl
import os
import pty
import select
import struct
import subprocess
import termios
import time
import unicodedata
from dataclasses import dataclass, field

WIDE = frozenset({"W", "F"})
ZERO = frozenset({"\u200b", "\u200d", "\ufe0e", "\ufe0f"})
BLANK = "\u0000"


@dataclass
class Screen:
    rows: int = 36
    columns: int = 100
    grid: list[list[str]] = field(init=False)
    row: int = field(init=False, default=0)
    column: int = field(init=False, default=0)
    pending: str = field(init=False, default="")
    decoder: codecs.IncrementalDecoder = field(init=False)

    def __post_init__(self) -> None:
        self.grid = [self._blank() for _ in range(self.rows)]
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def _blank(self) -> list[str]:
        return [" "] * self.columns

    def feed(self, data: bytes) -> None:
        text = self.decoder.decode(data)
        self.pending += text
        index = 0
        while index < len(self.pending):
            start = index
            char = self.pending[index]
            if char == "\x1b":
                following = self._escape(index)
                if following < 0:
                    self.pending = self.pending[start:]
                    return
                index = following
                continue
            if char == "\r":
                self.column = 0
            elif char == "\n":
                self._linefeed()
            elif char == "\b":
                self.column = max(0, self.column - 1)
            elif char == "\t":
                self.column = min(self.columns - 1, (self.column // 8 + 1) * 8)
            elif char.isprintable():
                self._put(char)
            index += 1
        self.pending = ""

    def _escape(self, index: int) -> int:
        if index + 1 >= len(self.pending):
            return -1
        marker = self.pending[index + 1]
        if marker == "[":
            end = index + 2
            while end < len(self.pending) and not ("@" <= self.pending[end] <= "~"):
                end += 1
            if end >= len(self.pending):
                return -1
            self._csi(self.pending[index + 2 : end], self.pending[end])
            return end + 1
        if marker == "]":
            end = index + 2
            while end < len(self.pending) and self.pending[end] not in "\x07":
                end += 1
            return len(self.pending) if end >= len(self.pending) else end + 1
        return index + 2

    def _csi(self, params: str, final: str) -> None:
        private = params.startswith("?")
        body = params[1:] if private else params
        numbers = [int(part) if part.isdigit() else 0 for part in body.split(";")]
        first = numbers[0] if numbers else 0
        if private or final in {"m", "h", "l", "q", "r", "s", "u"}:
            return
        if final == "A":
            self.row = max(0, self.row - max(1, first))
        elif final == "B":
            self.row = min(self.rows - 1, self.row + max(1, first))
        elif final == "C":
            self.column = min(self.columns - 1, self.column + max(1, first))
        elif final == "D":
            self.column = max(0, self.column - max(1, first))
        elif final == "E":
            self.row = min(self.rows - 1, self.row + max(1, first))
            self.column = 0
        elif final == "F":
            self.row = max(0, self.row - max(1, first))
            self.column = 0
        elif final == "G":
            self.column = min(self.columns - 1, max(1, first) - 1)
        elif final in {"H", "f"}:
            row = numbers[0] if numbers else 1
            column = numbers[1] if len(numbers) > 1 else 1
            self.row = min(self.rows - 1, max(1, row) - 1)
            self.column = min(self.columns - 1, max(1, column) - 1)
        elif final == "K":
            self._erase_line(first)
        elif final == "J":
            self._erase_screen(first)

    def _erase_line(self, mode: int) -> None:
        line = self.grid[self.row]
        if mode == 2:
            self.grid[self.row] = self._blank()
        elif mode == 0:
            for spot in range(self.column, self.columns):
                line[spot] = " "
        elif mode == 1:
            for spot in range(self.column + 1):
                line[spot] = " "

    def _erase_screen(self, mode: int) -> None:
        if mode == 2:
            self.grid = [self._blank() for _ in range(self.rows)]
            return
        if mode == 0:
            self._erase_line(0)
            for row in range(self.row + 1, self.rows):
                self.grid[row] = self._blank()
        elif mode == 1:
            self._erase_line(1)
            for row in range(self.row):
                self.grid[row] = self._blank()

    def _linefeed(self) -> None:
        self.row += 1
        if self.row >= self.rows:
            self.grid.pop(0)
            self.grid.append(self._blank())
            self.row = self.rows - 1

    def _put(self, char: str) -> None:
        width = 0 if char in ZERO or unicodedata.combining(char) else 1
        if unicodedata.east_asian_width(char) in WIDE:
            width = 2
        if width == 0:
            return
        if self.column + width > self.columns:
            self._linefeed()
            self.column = 0
        self.grid[self.row][self.column] = char
        if width == 2 and self.column + 1 < self.columns:
            self.grid[self.row][self.column + 1] = BLANK
        self.column += width

    def lines(self) -> list[str]:
        text = ["".join(cell for cell in line if cell != BLANK) for line in self.grid]
        while text and not text[-1].strip():
            text.pop()
        while text and not text[0].strip():
            text.pop(0)
        return text


CONTROL = {
    "enter": b"\r",
    "up": b"\x1b[A",
    "down": b"\x1b[B",
    "left": b"\x1b[D",
    "right": b"\x1b[C",
    "home": b"\x1b[H",
    "end": b"\x1b[F",
    "space": b" ",
    "tab": b"\t",
    "backspace": b"\x7f",
    "esc": b"\x1b",
    "ctrl-c": b"\x03",
}


@dataclass(frozen=True)
class Step:
    label: str
    keys: bytes
    wait: float = 0.0


def typing(text: str) -> Step:
    return Step(f'type "{text}"', text.encode())


def key(name: str) -> Step:
    keys = CONTROL.get(name)
    if keys is None:
        if len(name) != 1:
            raise KeyError(name)
        keys = name.encode()
    return Step(name, keys)


def parse_steps(spec: str) -> list[Step]:
    """Turn a story line into keystrokes.

    Steps split on ``|`` or newlines. A known key name is a key press, ``text:``
    forces typing, ``key:`` forces a key name, ``pause:`` waits, and anything
    else is typed, so ``/list`` and ``acct_nope`` need no prefix.
    """
    steps: list[Step] = []
    for raw in spec.replace("\n", "|").split("|"):
        token = raw.strip()
        if not token or token.startswith("#"):
            continue
        if token.startswith("pause:"):
            seconds = float(token[6:])
            steps.append(Step(f"pause {seconds:g}s", b"", wait=seconds))
        elif token.startswith("text:"):
            steps.append(typing(token[5:]))
        elif token.startswith("key:"):
            steps.append(key(token[4:]))
        elif token in CONTROL or len(token) == 1:
            steps.append(key(token))
        else:
            steps.append(typing(token))
    return steps


class Pty:
    """A child on a pty with a fixed window size and a live screen mirror."""

    def __init__(
        self,
        argv: list[str],
        *,
        env: dict[str, str],
        cwd: str,
        rows: int = 36,
        columns: int = 100,
    ) -> None:
        self.argv = argv
        self.env = env
        self.cwd = cwd
        self.rows = rows
        self.columns = columns
        self.screen = Screen(rows=rows, columns=columns)
        self.master = -1
        self.slave = -1
        self.process: subprocess.Popen[bytes] | None = None
        self.raw = bytearray()

    def start(self) -> None:
        master, slave = pty.openpty()
        size = struct.pack("HHHH", self.rows, self.columns, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, size)
        self.process = subprocess.Popen(
            self.argv,
            cwd=self.cwd,
            env=self.env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        self.master = master
        os.set_blocking(master, False)

    def pump(
        self,
        *,
        idle: float = 0.35,
        limit: float = 4.0,
        until_output: bool = False,
    ) -> None:
        end = time.monotonic() + limit
        last = time.monotonic()
        seen = bool(self.raw)
        while time.monotonic() < end:
            ready, _, _ = select.select([self.master], [], [], 0.03)
            if not ready:
                if (seen or not until_output) and time.monotonic() - last >= idle:
                    return
                continue
            try:
                chunk = os.read(self.master, 65536)
            except BlockingIOError, OSError:
                return
            if not chunk:
                return
            self.raw.extend(chunk)
            self.screen.feed(chunk)
            seen = True
            last = time.monotonic()

    def send(
        self,
        keys: bytes,
        *,
        idle: float = 0.35,
        limit: float = 4.0,
    ) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        try:
            os.write(self.master, keys)
        except OSError:
            return
        self.pump(idle=idle, limit=limit)

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.master >= 0:
            try:
                os.close(self.master)
            except OSError:
                pass


def show(screen: Screen) -> None:
    rows = screen.lines()
    width = max((len(line) for line in rows), default=0)
    print("    " + "\u250c" + "\u2500" * width + "\u2510")
    for line in rows:
        print("    \u2502" + line.ljust(width) + "\u2502")
    print("    " + "\u2514" + "\u2500" * width + "\u2518")
