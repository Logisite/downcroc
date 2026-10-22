from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_current: ContextVar[dict[str, Any] | None] = ContextVar(
    "downcroc_log_context", default=None
)


def current() -> dict[str, Any]:
    return dict(_current.get() or {})


@contextmanager
def bind(**fields: Any) -> Iterator[None]:
    token = _current.set({**(_current.get() or {}), **fields})
    try:
        yield
    finally:
        _current.reset(token)
