from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from downcroc.cli.client import api, get
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState

Path = tuple[str, ...]


@dataclass(frozen=True)
class Named:
    value: str
    label: str
    detail: str = ""


Resolver = Callable[[Ui, Path, LeafState], list[Named]]

_EXACT: dict[tuple[Path, str], Resolver] = {}
_GENERIC: dict[str, Resolver] = {}


def resolver(*dests: str, path: Path | None = None):
    def register(function: Resolver) -> Resolver:
        for dest in dests:
            if path is None:
                _GENERIC[dest] = function
            else:
                _EXACT[(path, dest)] = function
        return function

    return register


def has_resolver(path: Path, dest: str) -> bool:
    return (path, dest) in _EXACT or dest in _GENERIC


def resolve(ui: Ui, path: Path, dest: str, state: LeafState) -> list[Named]:
    function = _EXACT.get((path, dest)) or _GENERIC.get(dest)
    if function is None:
        return []
    try:
        return function(ui, path, state)
    except CliError:
        return []


def match(options: list[Named], text: str) -> Named | None:
    wanted = text.strip().casefold()
    if not wanted:
        return None
    for option in options:
        if option.value.casefold() == wanted or option.label.casefold() == wanted:
            return option
    for option in options:
        if wanted in option.label.casefold():
            return option
    return None


def fetch(ui: Ui, path: str, **params: object) -> list[dict]:
    paths, _, _ = load()
    with api(paths) as client:
        found = get(client, path, **params)
    if isinstance(found, list):
        return [row for row in found if isinstance(row, dict)]
    return []


def fetch_one(ui: Ui, path: str, **params: object) -> dict:
    del ui
    paths, _, _ = load()
    with api(paths) as client:
        found = get(client, path, **params)
    return found if isinstance(found, dict) else {}


def text(value: object) -> str:
    return "" if value is None else str(value)
