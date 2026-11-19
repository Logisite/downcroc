from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

from downcroc.cli.design.theme import DEFAULT, Theme
from downcroc.cli.ui.ansi import cells
from downcroc.runtime.logging.format import _display_stamp

LEVEL_TONE = {
    "debug": "fg_muted",
    "info": "info",
    "warning": "warning",
    "error": "danger",
    "critical": "danger",
}


@dataclass(frozen=True)
class Glyphs:
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    tee_down: str
    tee_up: str
    bead: str


UNICODE = Glyphs("╭", "╮", "╰", "╯", "─", "│", "┬", "┴", "◆")
ASCII = Glyphs("+", "+", "+", "+", "-", "|", "+", "+", "*")


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    text = hex_colour.lstrip("#")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _fg(hex_colour: str, *, bold: bool = False) -> str:
    red, green, blue = _rgb(hex_colour)
    head = "1;38;2" if bold else "38;2"
    return f"\x1b[{head};{red};{green};{blue}m"


RESET = "\x1b[0m"
DIM = "\x1b[2m"


def glyphs_for(choice: str) -> Glyphs:
    return ASCII if choice == "ascii" else UNICODE


def chain_width() -> int:
    columns = shutil.get_terminal_size((100, 24)).columns
    return max(20, columns - 2)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if cells(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _content(
    entry: dict[str, Any], utc: bool, theme: Theme
) -> list[tuple[str, str, bool]]:
    """Build content lines as (text, token, bold) segments.

    The header carries the level's semantic tone (blue info, amber warning, red
    error) and is bold, so the text is visibly coloured; structured fields are
    secondary and unbolded.
    """
    stamp = _display_stamp(entry, utc)
    level = str(entry.get("level", "info"))
    event = str(entry.get("event", ""))
    tone = LEVEL_TONE.get(level, "fg_primary")
    lines: list[tuple[str, str, bool]] = [
        (part, tone, True) for part in _wrap(f"{stamp}  {level}  {event}", 200)
    ]
    fields = "  ".join(
        f"{key}={value}"
        for key, value in entry.items()
        if key not in {"ts", "ts_local", "level", "logger", "event"}
    )
    if fields:
        lines.extend((part, "fg_secondary", False) for part in _wrap(fields, 200))
    return lines


def _box_lines(
    entry: dict[str, Any],
    glyphs: Glyphs,
    width: int,
    theme: Theme,
    colour: bool,
    utc: bool,
    top: str | None,
    bottom: str | None,
) -> list[str]:
    border = theme.info
    inner = width - 2
    text_width = inner - 2

    def paint(text: str, token: str, bold: bool = False) -> str:
        return _fg(theme.tone(token), bold=bold) + text + RESET if colour else text

    def edge(left: str, right: str, junction: str | None, tone: str) -> str:
        mid = width // 2
        row = list(glyphs.h * inner)
        if junction is not None:
            row[mid - 1] = junction
        body = left + "".join(row) + right
        if colour:
            return _fg(border) + body + RESET
        return body

    out = [edge(glyphs.tl, glyphs.tr, top, border)]
    for text, token, bold in _content(entry, utc, theme):
        for part in _wrap(text, text_width):
            pad = text_width - cells(part)
            out.append(
                (paint(glyphs.v, border) if colour else glyphs.v)
                + " "
                + paint(part, token, bold)
                + " " * (pad - 1)
                + (paint(glyphs.v, border) if colour else glyphs.v)
            )
    out.append(edge(glyphs.bl, glyphs.br, bottom, border))
    return out


def _bead_line(glyphs: Glyphs, width: int, theme: Theme, colour: bool) -> str:
    stem = " " * (width // 2 - 1) + glyphs.bead
    return _fg(theme.info) + stem + RESET if colour else stem


def render_chain(
    entries: list[dict[str, Any]],
    *,
    width: int | None = None,
    glyphs: Glyphs | None = None,
    theme: Theme = DEFAULT,
    colour: bool = True,
    utc: bool = False,
) -> str:
    """Render a whole list of events as one joined chain."""
    width = width or chain_width()
    glyphs = glyphs or UNICODE
    lines: list[str] = []
    count = len(entries)
    for index, entry in enumerate(entries):
        top = glyphs.tee_up if index else None
        bottom = glyphs.tee_down if index < count - 1 else None
        lines.extend(_box_lines(entry, glyphs, width, theme, colour, utc, top, bottom))
        if index < count - 1:
            lines.append(_bead_line(glyphs, width, theme, colour))
    return "\n".join(lines) + "\n"


class ChainRenderer:
    """Incremental renderer for --follow, emitting one event at a time."""

    def __init__(
        self,
        *,
        width: int | None = None,
        glyphs: Glyphs | None = None,
        theme: Theme = DEFAULT,
        colour: bool = True,
        utc: bool = False,
    ) -> None:
        self.width = width or chain_width()
        self.glyphs = glyphs or UNICODE
        self.theme = theme
        self.colour = colour
        self.utc = utc
        self.first = True

    def emit(self, entry: dict[str, Any]) -> str:
        parts: list[str] = []
        if not self.first:
            parts.append(_bead_line(self.glyphs, self.width, self.theme, self.colour))
        top = None if self.first else self.glyphs.tee_up
        parts.extend(
            _box_lines(
                entry,
                self.glyphs,
                self.width,
                self.theme,
                self.colour,
                self.utc,
                top,
                self.glyphs.tee_down,
            )
        )
        self.first = False
        return "\n".join(parts) + "\n"
