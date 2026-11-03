from __future__ import annotations

from dataclasses import dataclass, field

from downcroc.cli.errors import Cancelled
from downcroc.cli.parser import build_parser
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.editor import edit
from downcroc.cli.ui.tree.spec import CommandSpec, Tree, build_tree
from downcroc.cli.ui.tree.state import Globals, Session

MENU_ONLY = {
    ("account",),
    ("provider",),
    ("batch",),
    ("template",),
    ("job",),
    ("failed",),
    ("config",),
    ("mail",),
    ("vault",),
    ("stats",),
}


@dataclass
class Entry:
    label: str
    detail: str = ""
    node: CommandSpec | None = None
    preset: dict[str, str] = field(default_factory=dict)
    run: bool = False

    def option(self) -> prompts.Option:
        return prompts.Option(self.label, self, self.detail)


def open_path(ui: Ui, path: tuple[str, ...] = ()) -> bool:
    if not ui.interactive:
        return False
    tree = build_tree(build_parser())
    node = tree.root.find(path)
    if node is None:
        return False
    session = Session(Globals.from_ui(ui))
    if not _submenu(node):
        edit(
            ui, node, session.leaf(node.path), session.globals, tree.globals, fresh=True
        )
        return True
    _menu(ui, tree, node, session)
    return True


def _menu(ui: Ui, tree: Tree, node: CommandSpec, session: Session) -> None:
    stack: list[CommandSpec] = [node]
    visited: set[tuple[str, ...]] = set()
    while stack:
        current = stack[-1]
        try:
            chosen = prompts.choose(
                _title(current),
                [entry.option() for entry in _entries(current)],
                ui=ui,
                back=True,
            )
        except Cancelled:
            stack.pop()
            continue
        if chosen is None:
            stack.pop()
            continue
        entry = chosen if isinstance(chosen, Entry) else None
        if entry is None:
            continue
        if entry.node is not None and _submenu(entry.node):
            stack.append(entry.node)
            continue
        target = entry.node or current
        state = session.leaf(target.path)
        if entry.preset:
            state.preset(entry.preset)
        fresh = target.path not in visited
        visited.add(target.path)
        edit(
            ui,
            target,
            state,
            session.globals,
            tree.globals,
            fresh=fresh,
        )


def _submenu(node: CommandSpec) -> bool:
    return bool(node.children) or _choice_exposure(node) is not None


def _entries(node: CommandSpec) -> list[Entry]:
    if node.path in MENU_ONLY:
        return [_child(child) for child in node.children]
    if node.children:
        entries: list[Entry] = []
        if node.path:
            entries.append(
                Entry(
                    label=f"Run {node.path[-1]}",
                    detail=node.help or "run this command",
                    run=True,
                )
            )
        entries.extend(_child(child) for child in node.children)
        return entries
    choices = _choice_exposure(node)
    if choices:
        return [
            Entry(
                label=choice.replace("_", " "),
                detail=node.help,
                preset={choices.dest: choice},
                run=True,
            )
            for choice in choices.choices
        ]
    return [
        Entry(
            label=node.path[-1].replace("_", " ") if node.path else "Run",
            detail=node.help or "open this command",
            run=True,
        )
    ]


def _child(child: CommandSpec) -> Entry:
    return Entry(
        label=child.path[-1].replace("_", " "),
        detail=child.help,
        node=child,
    )


def _choice_exposure(node: CommandSpec):
    positionals = node.positionals
    if len(positionals) != 1:
        return None
    candidate = positionals[0]
    return candidate if candidate.choices else None


def _title(node: CommandSpec) -> str:
    if not node.path:
        return "downcroc"
    return "downcroc / " + " / ".join(part.replace("_", " ") for part in node.path)
