"""Page indexing, navigation, and route helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from downcroc.cli.docs.content.nodes import Document, Heading
from downcroc.cli.docs.content.parser import parse_document

NAV = {
    "": 0,
    "part-i": 1,
    "part-ii": 2,
    "part-iii": 3,
    "release-notes": 4,
}


@dataclass(frozen=True)
class IndexedPage:
    path: Path
    rel: str
    route: str
    title: str
    description: str
    doc: Document
    headings: tuple[Heading, ...]
    order: int = 0
    tags: tuple[str, ...] = ()
    meta: dict[str, object] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return self.rel.removesuffix(".md").replace("/", "-")


@dataclass(frozen=True)
class NavItem:
    title: str
    route: str
    rel: str
    level: int = 0
    children: tuple[NavItem, ...] = ()


@dataclass(frozen=True)
class DocIndex:
    root: Path
    pages: tuple[IndexedPage, ...]
    by_route: dict[str, IndexedPage]
    nav: tuple[NavItem, ...] = ()

    def get(self, route_or_rel: str) -> IndexedPage | None:
        key = _norm_route(route_or_rel)
        return self.by_route.get(key)

    def prev_next(self, route: str) -> tuple[IndexedPage | None, IndexedPage | None]:
        key = _norm_route(route)
        for i, page in enumerate(self.pages):
            if _norm_route(page.route) == key or _norm_route(page.rel) == key:
                prev = self.pages[i - 1] if i > 0 else None
                nxt = self.pages[i + 1] if i + 1 < len(self.pages) else None
                return prev, nxt
        return None, None


def _norm_route(value: str) -> str:
    v = value.strip().replace("\\", "/").strip("/")
    v = v.removesuffix(".md")
    if v == "index":
        return ""
    return v


def route_for(rel: str) -> str:
    return _norm_route(rel)


def _nav_key(root: Path, path: Path) -> tuple[int, int, str]:
    rel = path.relative_to(root).as_posix()
    section = rel.split("/", 1)[0] if "/" in rel else ""
    order = 0
    return (NAV.get(section, 99), order, rel)


def _tags(meta: dict[str, object]) -> tuple[str, ...]:
    v = meta.get("tags")
    if isinstance(v, tuple):
        return tuple(str(x) for x in v)
    if isinstance(v, str) and v:
        return (v,)
    return ()


def load_pages(root: Path) -> tuple[IndexedPage, ...]:
    pages: list[IndexedPage] = []
    paths = sorted(root.rglob("*.md"), key=lambda path: _nav_key(root, path))
    for path in paths:
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        doc = parse_document(source)
        route = route_for(rel)
        pages.append(
            IndexedPage(
                path=path,
                rel=rel,
                route=route,
                title=doc.title or rel,
                description=doc.description,
                doc=doc,
                headings=doc.headings,
                order=int(doc.meta.get("order") or 0),
                tags=_tags(doc.meta),
                meta=doc.meta,
            )
        )
    return tuple(pages)


def build_nav(pages: tuple[IndexedPage, ...]) -> tuple[NavItem, ...]:
    items: list[NavItem] = []
    for page in pages:
        items.append(NavItem(title=page.title, route=page.route, rel=page.rel, level=0))
    return tuple(items)


def build_index(root: Path) -> DocIndex:
    pages = load_pages(root)
    by_route: dict[str, IndexedPage] = {}
    for page in pages:
        by_route[_norm_route(page.route)] = page
        by_route[_norm_route(page.rel)] = page
    nav = build_nav(pages)
    return DocIndex(root=root, pages=pages, by_route=by_route, nav=nav)
