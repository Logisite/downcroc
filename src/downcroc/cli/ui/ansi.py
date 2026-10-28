from __future__ import annotations

import importlib.util
import os
import unicodedata

CSI = "\x1b["
RESET = f"{CSI}0m"
WIDE = frozenset({"W", "F"})
ZERO = frozenset({"\u200b", "\u200d", "\ufe0e", "\ufe0f"})


def strip(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "\x1b" and text.startswith("[", index + 1):
            index = _sequence_end(text, index)
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def _sequence_end(text: str, index: int) -> int:
    end = index + 2
    while end < len(text) and not ("@" <= text[end] <= "~"):
        end += 1
    return min(end + 1, len(text))


def _cell(char: str) -> int:
    if char in ZERO or unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in WIDE else 1


def cells(text: str) -> int:
    return sum(_cell(char) for char in strip(text))


def width(text: str) -> int:
    return cells(text)


def clip(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if cells(text) <= limit:
        return text
    return _cut(text, max(0, limit - 1)) + "~"


def _cut(text: str, budget: int) -> str:
    out: list[str] = []
    used = 0
    index = 0
    while index < len(text):
        if text[index] == "\x1b" and text.startswith("[", index + 1):
            end = _sequence_end(text, index)
            out.append(text[index:end])
            index = end
            continue
        size = _cell(text[index])
        if used + size > budget:
            break
        out.append(text[index])
        used += size
        index += 1
    joined = "".join(out)
    return joined + RESET if "\x1b" in joined else joined


def pad(text: str, limit: int) -> str:
    return text + " " * max(0, limit - cells(text))


def fit(text: str, limit: int) -> str:
    return clip(text, max(1, limit))


def clear_line() -> str:
    return f"{CSI}2K\r"


def move_up(lines: int) -> str:
    return "" if lines <= 0 else f"{CSI}{lines}A"


def move_down(lines: int) -> str:
    return "" if lines <= 0 else f"{CSI}{lines}B"


def move_right(columns: int) -> str:
    return "" if columns <= 0 else f"{CSI}{columns}C"


def hide_cursor() -> str:
    return f"{CSI}?25l"


def show_cursor() -> str:
    return f"{CSI}?25h"


def erase(lines: int) -> str:
    if lines <= 0:
        return ""
    return "\r" + (move_up(1) + clear_line()) * lines


def raw_available() -> bool:
    if os.name == "nt":
        return True
    return importlib.util.find_spec("termios") is not None
