from __future__ import annotations

from dataclasses import dataclass, field

from downcroc.cli.ui.session import DEFAULT_TIMEOUT_S, Ui

Value = str | bool | list[str] | None


@dataclass
class Globals:
    json: bool = False
    no_input: bool = False
    yes: bool = False
    wide: bool = False
    full: bool = False
    glyphs: str = "auto"
    color: str = "auto"
    quiet: bool = False
    timeout: float | None = None
    no_pager: bool = False

    @classmethod
    def from_ui(cls, ui: Ui) -> Globals:
        timeout = ui.timeout if ui.timeout != DEFAULT_TIMEOUT_S else None
        return cls(
            json=ui.json_mode,
            wide=ui.wide,
            full=ui.full,
            glyphs=ui.glyphs,
            color="always" if ui.colour else "auto",
            quiet=ui.quiet,
            timeout=timeout,
        )

    def get(self, dest: str) -> Value:
        return getattr(self, dest, None)

    def set(self, dest: str, value: Value) -> None:
        if hasattr(self, dest):
            setattr(self, dest, value)


@dataclass
class LeafState:
    values: dict[str, Value] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    def clone(self) -> LeafState:
        return LeafState(dict(self.values), dict(self.labels))

    def get(self, dest: str) -> Value:
        return self.values.get(dest)

    def set(self, dest: str, value: Value, label: str = "") -> None:
        if value in (None, "", []):
            self.values.pop(dest, None)
            self.labels.pop(dest, None)
            return
        self.values[dest] = value
        if label:
            self.labels[dest] = label
        else:
            self.labels.pop(dest, None)

    def preset(self, values: dict[str, str]) -> None:
        for dest, value in values.items():
            self.set(dest, value)

    def clear(self) -> None:
        self.values.clear()
        self.labels.clear()


@dataclass
class Session:
    globals: Globals
    leaves: dict[tuple[str, ...], LeafState] = field(default_factory=dict)

    def leaf(self, path: tuple[str, ...]) -> LeafState:
        return self.leaves.setdefault(path, LeafState())
