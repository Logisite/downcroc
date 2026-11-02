"""Diamond spine: one line per step, drawn down a single rule."""

from __future__ import annotations

import re
import sys
from typing import Self

from downcroc.cli.ui import ansi
from downcroc.cli.ui.session import Ui

UNICODE = {
    "done": "\u25c6",
    "active": "\u25c7",
    "fail": "\u2715",
    "line": "\u2502",
}

SPINNER = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"

MAX_WIDTH = 100
MIN_GAP = 2
TRAILING_ROWS = 3
SECONDS = re.compile(r"([0-9]+(?:\.[0-9]+)?)s")
WAIT = re.compile(r"([0-9]+(?:\.[0-9]+)?)s of ([0-9]+(?:\.[0-9]+)?)s")

TONE = {"done": "muted", "active": "accent", "fail": "bad"}

BAR_WIDTH = 12
BAR = ("\u25b0", "\u25b1")


def host_of(text: str) -> str:
    if " on " not in text:
        return ""
    return text.split(" on ", 1)[1].rstrip(" .")


def seconds_of(text: str) -> str:
    found = SECONDS.search(text)
    return f"{found.group(1)}s" if found else ""


def wait_bar(text: str) -> str:
    found = WAIT.search(text)
    if found is None:
        return seconds_of(text)
    elapsed = float(found.group(1))
    limit = max(0.1, float(found.group(2)))
    filled = round(BAR_WIDTH * min(1.0, elapsed / limit))
    fill, rest = BAR
    return (
        f"{fill * filled}{rest * (BAR_WIDTH - filled)}  {elapsed:.1f}s / {limit:.0f}s"
    )


class Spine:
    """Draw one node per step, and rewrite only the node still running."""

    def __init__(self, ui: Ui, stream=None) -> None:
        self.ui = ui
        self.stream = stream or sys.stdout
        self.glyphs = UNICODE
        self.frames = SPINNER
        self.live = bool(
            self.stream.isatty()
            and ui.interactive
            and not ui.json_mode
            and not ui.quiet
        )
        self._current: Node | None = None
        self._label = ""
        self._open = False
        self._drew = False
        self._gap = False
        self._spin = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, kind, value, trace) -> None:
        self.done()

    def spin(self) -> str:
        return self.frames[self._spin % len(self.frames)]

    def line(self, glyph: str, key: str, label: str, detail: str = "") -> str:
        limit = max(20, min(self.ui.width, MAX_WIDTH))
        head = ansi.clip(f"{glyph} {label}", limit)
        body = self.ui.paint(head, TONE[key])
        if not detail:
            return body
        room = limit - ansi.width(head) - MIN_GAP
        if room < 1:
            return body
        detail = ansi.clip(detail, room)
        gap = limit - ansi.width(head) - ansi.width(detail)
        return body + " " * gap + self.ui.dim(detail)

    def begin(self, label: str, detail: str = "") -> Node:
        self._settle_current()
        node = Node(self, label)
        self._current = node
        self._label = label
        self._open = False
        self._rewrite(self.line(self.spin(), "active", label, detail))
        self._open = True
        return node

    def _settle_current(self) -> None:
        node = self._current
        if node is not None and not node.closed:
            node.ok()

    def done(self) -> None:
        self._settle_current()
        if not self.live or not self._drew or self._gap:
            return
        self._gap = True
        self.stream.write("\n" * TRAILING_ROWS)
        self.stream.flush()

    def _write(self, text: str) -> None:
        if not self.live:
            return
        self.stream.write(text + "\n")
        self.stream.flush()
        self._drew = True

    def _rewrite(self, text: str) -> None:
        if not self.live:
            return
        if self._open:
            self.stream.write(ansi.move_up(1) + ansi.clear_line())
        self.stream.write(text + "\n")
        self.stream.flush()
        self._drew = True

    def _settle(self, node: Node, key: str, detail: str = "") -> None:
        if node.closed:
            return
        node.closed = True
        self._rewrite(self.line(self.glyphs[key], key, node.label, detail))
        self._open = False
        self._current = None
        self._write(self.ui.dim(self.glyphs["line"]))


class Node:
    def __init__(self, spine: Spine, label: str) -> None:
        self.spine = spine
        self.label = label
        self.closed = False

    def update(self, detail: str = "", spin: bool = True) -> None:
        if self.closed or self.spine._current is not self:
            return
        if spin:
            self.spine._spin += 1
            glyph = self.spine.spin()
        else:
            glyph = self.spine.glyphs["active"]
        self.spine._rewrite(self.spine.line(glyph, "active", self.label, detail))

    def ok(self, detail: str = "") -> None:
        self._finish("done", detail)

    def fail(self, detail: str = "") -> None:
        self._finish("fail", detail)

    def _finish(self, key: str, detail: str) -> None:
        if self.closed:
            return
        if self.spine._current is not self:
            self.closed = True
            return
        self.spine._settle(self, key, detail)


class StartReport:
    """Adapt the service lifecycle callback to spine nodes."""

    def __init__(self, spine: Spine) -> None:
        self.spine = spine
        self.node: Node | None = None
        self.stage = ""
        self.launch = ""

    def __call__(self, text: str, fraction: float | None) -> None:
        if fraction == 0.0:
            self.stage = "launch"
            self.launch = host_of(text)
            self.node = self.spine.begin("launch daemon", self.launch)
            return
        if fraction is None:
            if self.stage != "wait":
                if self.node is not None:
                    self.node.ok(self.launch)
                self.stage = "wait"
                self.node = self.spine.begin("wait for health")
            if self.node is not None:
                self.node.update(wait_bar(text), spin=False)
            return
        if self.stage == "wait" and self.node is not None:
            self.node.ok(f"ready in {seconds_of(text)}".rstrip())

    def fail(self, detail: str) -> None:
        if self.node is not None and not self.node.closed:
            first = detail.strip().splitlines()[0] if detail.strip() else "failed"
            self.node.fail(ansi.clip(first, 60))
