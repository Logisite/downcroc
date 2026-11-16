"""Frontmatter parsing helpers for docs markdown."""

from __future__ import annotations


def frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    meta: dict[str, object] = {}
    current = ""
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and current:
            key, _, value = line.strip().partition(":")
            meta[f"{current}_{key.strip()}"] = _value(value)
            continue
        key, _, value = line.partition(":")
        current = key.strip()
        meta[current] = _value(value)
    return meta, text[end + 5 :]


def _value(raw: str) -> object:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return tuple(
            item.strip().strip('"').strip("'")
            for item in value[1:-1].split(",")
            if item.strip()
        )
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value.strip('"').strip("'")
