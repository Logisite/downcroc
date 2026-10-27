from __future__ import annotations

import importlib.util
import os

CSI = "\x1b["


def strip(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "\x1b" and text.startswith("[", index + 1):
            end = index + 2
            while end < len(text) and not ("@" <= text[end] <= "~"):
                end += 1
            index = end + 1
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def width(text: str) -> int:
    return len(strip(text))


def clip(text: str, limit: int) -> str:
    plain = strip(text)
    if len(plain) <= limit:
        return text
    return plain[: max(0, limit - 1)] + "~"


def clear_line() -> str:
    return f"{CSI}2K\r"


def move_up(lines: int) -> str:
    return "" if lines <= 0 else f"{CSI}{lines}A"


def hide_cursor() -> str:
    return f"{CSI}?25l"


def show_cursor() -> str:
    return f"{CSI}?25h"


def erase(lines: int) -> str:
    if lines <= 0:
        return ""
    return move_up(lines) + (clear_line() + "\n") * lines + move_up(lines)


def raw_available() -> bool:
    if os.name == "nt":
        return True
    return importlib.util.find_spec("termios") is not None
