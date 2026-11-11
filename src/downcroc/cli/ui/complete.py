from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LIMIT = 100
TAB = "\t"


@dataclass(frozen=True)
class Completion:
    buffer: str
    cursor: int
    matches: tuple[str, ...] = ()
    truncated: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.matches) and len(self.matches) == 1


def complete(buffer: str, cursor: int) -> Completion:
    start = _token_start(buffer, cursor)
    token = buffer[start:cursor]
    quoted = token[:1] in {'"', "'"}
    if quoted:
        token = token[1:]
    display_dir, prefix = os.path.split(token)
    lookup_dir = os.path.expanduser(display_dir or ".")
    try:
        entries = list(os.scandir(lookup_dir))
    except OSError:
        return Completion(buffer, cursor)
    names = sorted((entry.name, entry.is_dir()) for entry in entries)
    folded = prefix.casefold() if os.name == "nt" else prefix
    chosen = [
        (name, is_dir)
        for name, is_dir in names
        if (name.casefold() if os.name == "nt" else name).startswith(folded)
    ]
    truncated = len(chosen) > LIMIT
    chosen = chosen[:LIMIT]
    if not chosen:
        return Completion(buffer, cursor)
    if len(chosen) == 1:
        name, is_dir = chosen[0]
        value = _join(display_dir, name, is_dir)
        return Completion(_replace(buffer, start, cursor, value), start + len(value))
    common = _common([name for name, _ in chosen])
    if len(common) <= len(prefix):
        return Completion(
            buffer,
            cursor,
            tuple(_join(display_dir, name, is_dir) for name, is_dir in chosen[:8]),
            truncated,
        )
    value = _join(display_dir, common, False)
    return Completion(
        _replace(buffer, start, cursor, value),
        start + len(value),
        tuple(_join(display_dir, name, is_dir) for name, is_dir in chosen[:8]),
        truncated,
    )


def _token_start(buffer: str, cursor: int) -> int:
    spot = cursor
    while spot and buffer[spot - 1] not in {" ", TAB}:
        spot -= 1
    return spot


def _replace(buffer: str, start: int, cursor: int, value: str) -> str:
    return buffer[:start] + value + buffer[cursor:]


def _join(directory: str, name: str, is_dir: bool) -> str:
    value = os.path.join(directory, name) if directory else name
    if is_dir and not value.endswith(os.sep):
        value += os.sep
    if os.name == "nt":
        value = value.replace("/", "\\")
    if " " in value and not (value.startswith('"') and value.endswith('"')):
        value = f'"{value}"'
    return value


def _common(names: list[str]) -> str:
    if not names:
        return ""
    head = names[0]
    for name in names[1:]:
        index = 0
        while index < len(head) and index < len(name) and head[index] == name[index]:
            index += 1
        head = head[:index]
        if not head:
            break
    return head


def expand_quotes(path: str | Path) -> str:
    text = str(path)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text
