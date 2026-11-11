from __future__ import annotations

from typing import Any

SECRET_MARKERS = ("token", "secret", "password", "authorization")


def scrub_entry(entry: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(entry.items()):
        if _secret_key(key):
            entry[key] = "[redacted]"
        elif isinstance(value, dict):
            entry[key] = scrub_entry(value)
    return entry


def _secret_key(key: str) -> bool:
    lowered = key.casefold()
    return any(marker in lowered for marker in SECRET_MARKERS)
