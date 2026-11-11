from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from rich.console import Console

from downcroc.cli.docs import model, search
from downcroc.cli.docs.render import page_renderable
from downcroc.cli.errors import CliError
from downcroc.cli.output import colour_enabled, json_out
from downcroc.cli.ui.session import Ui, build


def book_root() -> Path | None:
    package = Path(__file__).resolve().parents[2]
    candidates = (
        package / "docs",
        package.parent / "docs",
        package.parent.parent / "docs",
        Path.cwd() / "docs",
    )
    for candidate in candidates:
        if (candidate / "index.md").is_file():
            return candidate
    return None


def _pages() -> list[model.Page]:
    root = book_root()
    if root is None:
        raise CliError(
            "the documentation book is not installed",
            code="docs_missing",
            hint="reinstall downcroc or run from a checkout",
        )
    return model.load_pages(root)


def _find(pages: list[model.Page], wanted: str) -> model.Page:
    key = wanted.strip().removesuffix(".md").strip("/")
    for page in pages:
        if page.rel.removesuffix(".md") == key:
            return page
    matches = [page for page in pages if page.title.casefold() == key.casefold()]
    if len(matches) == 1:
        return matches[0]
    matches = [page for page in pages if key.casefold() in page.slug.casefold()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(page.rel for page in matches[:8])
        raise CliError(
            f"topic {wanted} is ambiguous",
            code="docs_ambiguous",
            hint=f"choose one: {names}",
            exit_code=2,
        )
    raise CliError(
        f"no docs topic named {wanted}",
        code="docs_topic_not_found",
        hint="run downcroc docs --list or downcroc docs --search QUERY",
        exit_code=2,
    )


def _list(ui: Ui, pages: list[model.Page]) -> int:
    if ui.json_mode:
        json_out(
            [
                {
                    "path": page.rel,
                    "title": page.title,
                    "section": page.rel.split("/", 1)[0] if "/" in page.rel else "",
                    "summary": page.summary or page.description,
                    "tags": list(page.tags),
                }
                for page in pages
            ]
        )
        return 0
    section = ""
    for page in pages:
        current = page.rel.split("/", 1)[0] if "/" in page.rel else ""
        if current != section:
            section = current
            print(ui.bold(section.title() if section else page.title))
        label = f"  {page.title}"
        summary = page.summary or page.description
        print(f"{label:<34} {ui.dim(summary)}" if summary else label)
    return 0


def _search(ui: Ui, pages: list[model.Page], query: str) -> int:
    hits = search.search(pages, query)
    if ui.json_mode:
        json_out(
            [
                {
                    "path": hit.page.rel,
                    "title": hit.page.title,
                    "line": hit.line,
                    "score": round(hit.score, 2),
                }
                for hit in hits
            ]
        )
        return 0 if hits else 1
    if not hits:
        print(f"no matches for {query}", file=sys.stderr)
        return 1
    for hit in hits:
        print(ui.bold(hit.page.title), ui.dim(hit.page.rel))
        if hit.line:
            print(f"  {hit.line}")
    return 0


def _render(page: model.Page, args: object, ui: Ui) -> int:
    width = getattr(args, "width", None)
    if width is None:
        width = min(100, max(40, ui.width))
    console = Console(
        width=width,
        force_terminal=sys.stdout.isatty() and not ui.json_mode,
        color_system="truecolor" if colour_enabled() and not ui.json_mode else None,
        soft_wrap=False,
    )
    renderable = page_renderable(page, width, plain=ui.json_mode)
    if (
        sys.stdout.isatty()
        and not getattr(args, "no_pager", False)
        and not ui.json_mode
    ):
        with console.pager(styles=True):
            console.print(renderable)
    else:
        console.print(renderable)
    return 0


def _interactive(pages: list[model.Page]) -> int:
    from downcroc.cli.docs.app import DocsApp

    DocsApp(pages).run()
    return 0


def run(args: object) -> int:
    ui = build(args)
    pages = _pages()
    if getattr(args, "list", False):
        return _list(ui, pages)
    query = getattr(args, "search", None)
    if query:
        return _search(ui, pages, query)
    topic = getattr(args, "topic", None)
    if (
        not topic
        and not getattr(args, "raw", False)
        and not getattr(args, "open", False)
    ):
        if ui.interactive:
            return _interactive(pages)
        topic = "index"
    page = _find(pages, topic or "index")
    if getattr(args, "raw", False):
        sys.stdout.write(page.raw)
        if not page.raw.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    if getattr(args, "open", False):
        webbrowser.open(Path(page.path).as_uri())
        return 0
    return _render(page, args, ui)
