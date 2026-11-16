"""Slug/id helpers for headings and anchors."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_EDGE = re.compile(r"(^-|-$)")


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = norm.lower()
    norm = _NON_ALNUM.sub("-", norm)
    norm = _EDGE.sub("", norm)
    return norm or "section"


def unique_slug(text: str, seen: dict[str, int]) -> str:
    base = slugify(text)
    count = seen.get(base, 0)
    seen[base] = count + 1
    if count == 0:
        return base
    return f"{base}-{count}"
