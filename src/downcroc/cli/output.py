from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Any

from downcroc.cli.ui import ansi

MAX_CELL = 48
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOX = {
    "tl": "\u256d",
    "tr": "\u256e",
    "bl": "\u2570",
    "br": "\u256f",
    "h": "\u2500",
    "v": "\u2502",
    "top": "\u252c",
    "bottom": "\u2534",
    "cross": "\u253c",
    "left": "\u251c",
    "right": "\u2524",
}

GOOD = {
    "connected",
    "done",
    "sent",
    "ok",
    "enabled",
    "active",
    "ready",
    "delivered",
    "confirmed",
    "running",
    "unlocked",
}
WAITING = {
    "pending",
    "queued",
    "sending",
    "awaiting_approval",
    "verifying",
    "unverified",
    "retry_wait",
    "paused",
    "waiting",
    "requested",
    "probable",
    "locked",
    "stopped",
}
BAD = {
    "failed",
    "needs_reauth",
    "disabled",
    "cancelled",
    "bounced",
    "error",
    "invalid",
    "missing",
    "stale",
    "unreachable",
    "corrupt",
}

_CONTEXT = {"wide": False, "full": False}


def configure(*, wide: bool = False, full: bool = False) -> None:
    _CONTEXT["wide"] = wide
    _CONTEXT["full"] = full


def is_full() -> bool:
    return bool(_CONTEXT["full"])


def colour_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _paint(text: str, colour: str | None) -> str:
    if colour is None or not colour_enabled():
        return text
    return f"{colour}{text}{RESET}"


def _value_colour(text: str) -> str | None:
    key = text.casefold()
    if key in GOOD:
        return GREEN
    if key in WAITING:
        return YELLOW
    if key in BAD:
        return RED
    return None


def json_out(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    text = " ".join(str(value).split())
    if len(text) <= MAX_CELL or _CONTEXT["full"] or _CONTEXT["wide"]:
        return text
    if not any(character.isspace() for character in text):
        return text
    keep = max(8, MAX_CELL - 18)
    return f"{text[:keep].rstrip()}... (+{len(text) - keep} chars)"


def table(headers: list[str], rows: list[list[Any]]) -> None:
    if not headers:
        return
    cooked = [_text_row(row, len(headers)) for row in rows]
    live = _terminal_width()
    widths = _layout(headers, cooked, live)
    if widths is None:
        _stacked(headers, cooked, live)
        return
    _grid(headers, cooked, widths)


def _text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    return " ".join(str(value).split())


def _text_row(row: list[Any], count: int) -> list[str]:
    values = [_text(value) for value in row[:count]]
    return values + [""] * (count - len(values))


def _terminal_width() -> int:
    live = shutil.get_terminal_size((100, 24)).columns
    return live if _CONTEXT["wide"] else min(live, 120)


def _take(text: str, width: int) -> tuple[str, str]:
    used = 0
    index = 0
    while index < len(text):
        size = ansi.cells(text[index])
        if used + size > width:
            break
        used += size
        index += 1
    return text[:index], text[index:]


def _wrap(text: str, width: int) -> list[str]:
    if width <= 0:
        return [text]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    line = ""
    for word in words:
        while ansi.cells(word) > width:
            head, word = _take(word, width)
            if not head:
                break
            if line:
                lines.append(line)
                line = ""
            lines.append(head)
        candidate = f"{line} {word}".strip()
        if ansi.cells(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
    if line or not lines:
        lines.append(line)
    return lines


def _layout(
    headers: list[str],
    rows: list[list[str]],
    live: int,
) -> list[int] | None:
    natural = [ansi.cells(header) for header in headers]
    columns: list[list[str]] = [[] for _ in headers]
    for row in rows:
        for index, value in enumerate(row):
            natural[index] = max(natural[index], ansi.cells(value))
            columns[index].append(value)
    floors = [
        _floor(header, columns[index], natural[index], index)
        for index, header in enumerate(headers)
    ]
    available = live - (3 * len(headers) + 1)
    if available < sum(floors):
        return None
    widths = list(floors)
    remaining = available - sum(widths)
    for index in range(len(widths)):
        need = natural[index] - widths[index]
        if 0 < need <= 12 and need <= remaining:
            widths[index] += need
            remaining -= need
    weights = [natural[index] - widths[index] for index in range(len(widths))]
    total = sum(weights)
    if total and remaining:
        used = 0
        for index, weight in enumerate(weights):
            take = min(weight, remaining * weight // total)
            widths[index] += take
            weights[index] -= take
            used += take
        remaining -= used
    while remaining > 0:
        index = max(range(len(weights)), key=lambda spot: weights[spot], default=0)
        if weights[index] <= 0:
            break
        widths[index] += 1
        weights[index] -= 1
        remaining -= 1
    return widths


def _floor(header: str, values: list[str], natural: int, index: int) -> int:
    if any(" " in value for value in values):
        return min(natural, max(ansi.cells(header), 8))
    if index == 0:
        return min(natural, 24)
    return min(natural, 16)


def _rule(widths: list[int], left: str, middle: str, right: str) -> str:
    cells = [BOX["h"] * (width + 2) for width in widths]
    return _paint(left + middle.join(cells) + right, DIM)


def _bar() -> str:
    return _paint(BOX["v"], DIM)


def _line(values: list[str], widths: list[int], colours: list[str | None]) -> None:
    wrapped = [_wrap(value, width) for value, width in zip(values, widths)]
    height = max((len(lines) for lines in wrapped), default=1)
    for index in range(height):
        parts = []
        for lines, width, colour in zip(wrapped, widths, colours):
            value = lines[index] if index < len(lines) else ""
            parts.append(" " + _paint(ansi.pad(value, width), colour) + " ")
        print(_bar() + _bar().join(parts) + _bar())


def _grid(headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    print(_rule(widths, BOX["tl"], BOX["top"], BOX["tr"]))
    _line(headers, widths, [BOLD + CYAN] * len(headers))
    print(_rule(widths, BOX["left"], BOX["cross"], BOX["right"]))
    for index, row in enumerate(rows):
        if index:
            print(_rule(widths, BOX["left"], BOX["cross"], BOX["right"]))
        _line(row, widths, [_value_colour(value) for value in row])
    print(_rule(widths, BOX["bl"], BOX["bottom"], BOX["br"]))


def _stacked(headers: list[str], rows: list[list[str]], live: int) -> None:
    label = min(14, max((ansi.cells(header) for header in headers), default=4))
    room = max(8, live - label - 4)
    rule = BOX["h"] * max(8, min(live - 1, 60))
    for index, row in enumerate(rows):
        if index:
            print(_paint(rule, DIM))
        for header, value in zip(headers, row):
            lines = _wrap(value, room)
            for line_index, line in enumerate(lines):
                name = header if line_index == 0 else ""
                print(
                    _paint(name.ljust(label), BOLD)
                    + "  "
                    + _paint(line, _value_colour(value))
                )


def record(values: dict[str, Any]) -> None:
    if not values:
        return
    width = max(len(key) for key in values)
    for key, value in values.items():
        text = cell(value)
        print(f"{_paint(key.ljust(width), BOLD)}  {_paint(text, _value_colour(text))}")


def section(title: str, values: dict[str, Any]) -> None:
    print()
    print(_paint(title, BOLD))
    record(values)


def empty(message: str) -> None:
    print(message)


def footer(text: str) -> None:
    print()
    print(text)


def page_footer(
    shown: int,
    total: int | None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> None:
    if total is None or total <= shown and offset == 0:
        return
    first = offset + 1 if shown else 0
    last = offset + shown
    print()
    line = f"showing {first:,}-{last:,} of {total:,}"
    following = offset + (limit or shown)
    if following < total:
        line += f"  next: --offset {following}"
    print(line)


def flatten(document: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in document.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        else:
            flat[path] = value
    return flat
