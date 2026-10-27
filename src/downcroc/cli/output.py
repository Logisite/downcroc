from __future__ import annotations

import json
import os
import sys
from typing import Any

MAX_CELL = 48
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"

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
    cooked = [[cell(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in cooked:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print(
        "  ".join(
            _paint(header.ljust(width), BOLD + CYAN)
            for header, width in zip(headers, widths)
        )
    )
    print("  ".join(_paint("-" * width, DIM) for width in widths))
    for row in cooked:
        print(
            "  ".join(
                _paint(value.ljust(width), _value_colour(value))
                for value, width in zip(row, widths)
            )
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
