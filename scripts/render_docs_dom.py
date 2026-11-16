#!/usr/bin/env python3
"""Render the Textual docs app DOM as an ANSI/text tree (shadcn-mapping aid)."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.tree import Tree


def add_node(tree: Tree, node) -> None:
    ident = getattr(node, "id", None)
    classes = " ".join(sorted(getattr(node, "classes", []) or []))
    label = Text()
    label.append(node.__class__.__name__, style="bold cyan")
    if ident:
        label.append(f" #{ident}", style="green")
    if classes:
        label.append(f" .{classes.replace(' ', '.')}", style="yellow")
    if hasattr(node, "can_focus") and node.can_focus:
        label.append(" [focusable]", style="magenta")
    branch = tree.add(label)
    for child in list(getattr(node, "children", []) or []):
        add_node(branch, child)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="src/downcroc/docs")
    parser.add_argument("--size", default="140x40")
    parser.add_argument("--out", default="/tmp/opencode/docs_dom_tree.txt")
    parser.add_argument("--ansi", default="/tmp/opencode/docs_dom_tree.ansi.txt")
    args = parser.parse_args()
    w_s, h_s = args.size.lower().split("x", 1)
    size = (int(w_s), int(h_s))

    from downcroc.cli.docs.app import DocsApp
    from downcroc.cli.docs.content.index import build_index

    idx = build_index(Path(args.docs))
    app = DocsApp(idx.pages)
    console = Console(
        force_terminal=True,
        color_system="truecolor",
        width=max(size[0], 100),
        record=True,
    )
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        root = Tree("[bold]DocsApp DOM (Textual mapped to shadcn-like regions)[/bold]")
        add_node(root, app)
        console.print(root)

    text = console.export_text(clear=False)
    Path(args.out).write_text(text, encoding="utf-8")
    Path(args.ansi).write_text(console.export_text(styles=True, clear=False), encoding="utf-8")
    print(f"wrote {args.out} and {args.ansi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
