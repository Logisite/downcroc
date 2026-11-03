from __future__ import annotations

from downcroc.cli.parser import build_parser
from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.spec import build_tree
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import Named, resolver, text


@resolver("topic", path=("help",))
def topics(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del ui, path, state
    tree = build_tree(build_parser())
    return [
        Named(child.path[-1], child.path[-1], text(child.help))
        for child in tree.root.children
    ]
