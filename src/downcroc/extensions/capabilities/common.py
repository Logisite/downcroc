from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from downcroc.extensions.broker import Invocation


def dump(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {key: dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump(item) for item in value]
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def limit(inv: Invocation) -> int:
    return min(500, max(1, int(inv.param("limit", 100))))


def offset(inv: Invocation) -> int:
    return max(0, int(inv.param("offset", 0)))


def require(inv: Invocation, name: str) -> str:
    value = inv.param(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {name}")
    return value
