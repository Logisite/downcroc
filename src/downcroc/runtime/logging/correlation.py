from __future__ import annotations

from contextvars import ContextVar

_CORRELATION: ContextVar[str | None] = ContextVar("downcroc_correlation", default=None)


def current() -> str | None:
    return _CORRELATION.get()


def set_current(value: str | None):
    return _CORRELATION.set(value)


def reset(token) -> None:
    _CORRELATION.reset(token)
