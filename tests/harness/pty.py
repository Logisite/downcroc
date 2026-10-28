from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pyte

from tests.conftest import Stack

ROOT = Path(__file__).resolve().parents[2]
STARTUP_TIMEOUT_S = 60.0


class Session:
    """Drive the real CLI through a pseudo terminal and read the screen back."""

    def __init__(
        self,
        stack: Stack,
        *args: str,
        width: int = 80,
        height: int = 24,
    ) -> None:
        self.width = width
        self.height = height
        self.raw = b""
        self._master, slave = pty.openpty()
        self._size(width, height)
        self.process = subprocess.Popen(
            [sys.executable, "-m", "downcroc", *args],
            cwd=ROOT,
            env={**stack.daemon.environment(), "TERM": "xterm-256color"},
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)

    def wait_for(self, needle: bytes, timeout: float = STARTUP_TIMEOUT_S) -> None:
        deadline = time.monotonic() + timeout
        while needle not in self.raw and time.monotonic() < deadline:
            self.raw += self.drain(0.1)
        assert needle in self.raw, self.screen()

    def write(self, keys: bytes, seconds: float = 0.25) -> bytes:
        os.write(self._master, keys)
        chunk = self.drain(seconds)
        self.raw += chunk
        return chunk

    def drain(self, seconds: float) -> bytes:
        output = b""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ready, _, _ = select.select([self._master], [], [], 0.05)
            if not ready:
                continue
            try:
                chunk = os.read(self._master, 65536)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        return output

    def resize(self, width: int, height: int | None = None) -> None:
        self.width = width
        self.height = height or self.height
        self._size(self.width, self.height)

    def screen(self) -> list[str]:
        screen = pyte.Screen(self.width, self.height)
        pyte.Stream(screen).feed(self.raw.decode("utf-8", "replace"))
        return list(screen.display)

    def filled(self) -> list[int]:
        return [row for row, line in enumerate(self.screen()) if line.strip()]

    def bare_newlines(self) -> int:
        return self.raw.count(b"\n") - self.raw.count(b"\r\n")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=10)
        os.close(self._master)

    def _size(self, width: int, height: int) -> None:
        fcntl.ioctl(
            self._master,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", height, width, 0, 0),
        )
