from __future__ import annotations

import json
from pathlib import Path

from downcroc.domain.errors import InputUnreadable


def read_source(path: Path, max_bytes: int) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise InputUnreadable(f"cannot read {path}: {error.strerror}") from error
    if not path.is_file():
        raise InputUnreadable(f"{path} is not a file")
    if size > max_bytes:
        raise InputUnreadable(
            f"{path} is {size} bytes, above the {max_bytes} byte limit",
            hint="split the file or raise intake.max_file_bytes",
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise InputUnreadable(f"cannot read {path}: {error.strerror}") from error


def detect(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InputUnreadable("source is not valid UTF-8") from error
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            raise InputUnreadable(
                f"source looks like JSON but does not parse: {error}"
            ) from error
        return "json"
    if not stripped:
        raise InputUnreadable("source is empty")
    if "\n" not in stripped and "," not in stripped:
        raise InputUnreadable("source is neither a JSON campaign nor a CSV file")
    return "csv"


def decode(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InputUnreadable("source is not valid UTF-8") from error
