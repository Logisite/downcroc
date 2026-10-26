from __future__ import annotations

import secrets
from pathlib import Path

from downcroc.runtime.fs import atomic_write, restrict_owner

TOKEN_BYTES = 32


def issue(path: Path) -> str:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    atomic_write(path, token.encode("ascii"))
    restrict_owner(path)
    return token


def read(path: Path) -> str | None:
    try:
        token = path.read_text(encoding="ascii").strip()
    except OSError:
        return None
    return token or None


def clear(path: Path) -> None:
    path.unlink(missing_ok=True)
