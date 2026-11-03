from __future__ import annotations

from dataclasses import dataclass, field

from downcroc.cli.errors import Cancelled
from downcroc.cli.parser import build_parser
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.editor import edit, require
from downcroc.cli.ui.tree.execute import execute
from downcroc.cli.ui.tree.spec import CommandSpec, Tree, build_tree
from downcroc.cli.ui.tree.state import Globals, LeafState, Session

MENU_ONLY = {
    ("account",),
    ("account", "transport"),
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
    count: int = 0

    def option(self) -> prompts.Option:
        label = self.label
        if self.count:
            label = f"{label}  ({self.count})"
        return prompts.Option(label, self, self.detail)


def open_path(ui: Ui, path: tuple[str, ...] = ()) -> bool:
    if not ui.interactive:
        return False
    tree = build_tree(build_parser())
    node = tree.root.find(path)
    if node is None:
        return False
    session = Session(Globals.from_ui(ui))
    if not _submenu(node):
        _run(ui, node, session.leaf(node.path), session.globals)
        return True
    _menu(ui, tree, node, session)
    return True


def _menu(ui: Ui, tree: Tree, node: CommandSpec, session: Session) -> None:
    stack: list[CommandSpec] = [node]
    while stack:
        current = stack[-1]
        entries = _entries(current)
        try:
            chosen = prompts.choose(
                _title(current),
                [entry.option() for entry in entries],
                ui=ui,
                back=True,
                quit_=True,
                options_key=True,
            )
        except prompts.Quit:
            if _confirm_quit(ui):
                return
            continue
        except Cancelled:
            stack.pop()
            continue
        if chosen is None:
            stack.pop()
            continue
        if isinstance(chosen, prompts.OptionsRequest):
            entry = entries[chosen.index]
            target = entry.node or current
            state = session.leaf(target.path)
            if entry.preset:
                state.preset(entry.preset)
            result = edit(ui, target, state, session.globals, tree.globals)
            if result == "quit" and _confirm_quit(ui):
                return
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
        _run(ui, target, state, session.globals)


def _run(ui: Ui, spec: CommandSpec, state: LeafState, globals: Globals) -> None:
    try:
        require(ui, spec, state, globals)
    except Cancelled:
        return
    code, message, _ = execute(spec, state, globals)
    if code or message:
        print(ui.result(code == 0, f"exit {code}", message))


def _confirm_quit(ui: Ui) -> bool:
    try:
        return prompts.confirm("Quit downcroc?", ui=ui, default=False)
    except Cancelled:
        return False


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
                    count=len(node.options),
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
                count=len(node.options),
            )
            for choice in choices.choices
        ]
    return [
        Entry(
            label=node.path[-1].replace("_", " ") if node.path else "Run",
            detail=node.help or "open this command",
            run=True,
            count=len(node.options),
        )
    ]


def _child(child: CommandSpec) -> Entry:
    return Entry(
        label=child.path[-1].replace("_", " "),
        detail=child.help,
        node=child,
        count=len(child.options),
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
