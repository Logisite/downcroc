from __future__ import annotations

from pathlib import Path

from rich.console import Group

from downcroc.cli.design.theme import DEFAULT
from downcroc.cli.docs import model
from downcroc.cli.docs.content.parser import parse_document
from downcroc.cli.docs.md_render import render_page as render_page_v2


def page_renderable(
    page: model.Page,
    width: int,
    *,
    plain: bool = False,
    prev_next: tuple[tuple[str, str] | None, tuple[str, str] | None] | None = None,
) -> Group:
    del plain
    source = _page_source(page)
    doc = parse_document(source)
    return render_page_v2(
        doc,
        title=page.title or doc.title,
        description=page.description or doc.description,
        breadcrumbs=_breadcrumbs(page),
        prev_next=prev_next,
        theme=DEFAULT,
        width=max(32, width),
    )


def _page_source(page: model.Page) -> str:
    path = getattr(page, "path", None)
    if path:
        p = Path(path)
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raw = getattr(page, "raw", None)
    if isinstance(raw, str) and raw:
        return raw
    body = getattr(page, "body", "")
    return body if isinstance(body, str) else ""


def _breadcrumbs(page: model.Page) -> list[str]:
    if page.rel == "index.md":
        return ["Home"]
    parts = page.rel.removesuffix(".md").split("/")
    crumbs = ["Home"]
    if len(parts) > 1:
        crumbs.extend(parts[:-1])
    crumbs.append(page.title)
    return crumbs


def home_renderable(page: model.Page, width: int, *, plain: bool = False) -> Group:
    return page_renderable(page, width, plain=plain)


# Legacy block-level renderer removed in favor of typed markdown pipeline (Phase 4).
