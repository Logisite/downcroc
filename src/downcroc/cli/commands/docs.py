from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui.session import build


def _book() -> Path | None:
    package = Path(__file__).resolve().parents[2]
    for candidate in (package / "docs", package.parent / "docs"):
        if (candidate / "index.md").is_file() or (candidate / "index.html").is_file():
            return candidate
    return None


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    book = _book()
    index = ""
    if book is not None:
        index = str(
            book / "index.html"
            if (book / "index.html").is_file()
            else book / "index.md"
        )
    if ui.json_mode:
        json_out(
            {
                "book": str(book) if book else None,
                "index": index or None,
                "config": str(paths.config),
                "data": str(paths.data),
                "state": str(paths.state),
                "log": str(paths.log_file),
            }
        )
        return 0
    if book is None:
        record(
            {
                "book": "not installed alongside this package",
                "config": str(paths.config),
                "data": str(paths.data),
                "state": str(paths.state),
                "log": str(paths.log_file),
            }
        )
        if not ui.quiet:
            print("next: downcroc help")
        return 0
    record({"book": str(book), "index": index})
    if not ui.quiet:
        print(f"next: downcroc docs --open, or read {index}")
    if getattr(args, "open", False):
        opened = webbrowser.open(Path(index).as_uri())
        if not opened:
            print("could not open a browser", file=sys.stderr)
            raise CliError(
                "no browser is available",
                code="no_browser",
                hint=f"open {index} yourself",
            )
    return 0
