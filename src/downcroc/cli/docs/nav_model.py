"""Navigation grouping helpers for the docs shell/sidebar."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

SECTION_LABELS = {
    "": "Home",
    "part-i": "Part I · The Craft",
    "part-ii": "Part II · Commands",
    "part-iii": "Part III · The Machine",
    "release-notes": "Release Notes",
}


@dataclass(frozen=True)
class NavGroup:
    key: str
    label: str
    items: tuple[tuple[str, str, str], ...]  # (route/id, title, rel)


def section_for_rel(rel: str) -> str:
    return rel.split("/", 1)[0] if "/" in rel else ""


def group_pages(pages) -> list[NavGroup]:
    buckets: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for page in pages:
        rel = getattr(page, "rel", "")
        route = getattr(page, "route", "") or rel.removesuffix(".md")
        if route == "index":
            route = ""
        title = getattr(page, "title", rel)
        key = section_for_rel(rel)
        buckets[key].append((route or rel, title, rel))
    ordered_keys = sorted(
        buckets.keys(),
        key=lambda k: (0, k) if k == "" else (1, SECTION_LABELS.get(k, k)),
    )
    groups: list[NavGroup] = []
    for key in ordered_keys:
        label = SECTION_LABELS.get(key, key.replace("-", " ").title() or "Docs")
        groups.append(NavGroup(key=key, label=label, items=tuple(buckets[key])))
    return groups
