from __future__ import annotations

from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import (
    Named,
    fetch_one,
    resolver,
    text,
)


@resolver("key", path=("config", "set"))
def fields(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path, state
    schema = fetch_one(ui, "/api/config/schema")
    return [
        Named(
            text(field.get("path")),
            text(field.get("path")),
            f"{text(field.get('type'))}  {text(field.get('description'))}",
        )
        for field in schema.get("fields") or []
    ]


@resolver("value", path=("config", "set"))
def values(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path
    key = state.get("key")
    if not key:
        return []
    schema = fetch_one(ui, "/api/config/schema")
    for field in schema.get("fields") or []:
        if field.get("path") != key:
            continue
        return [
            Named(text(choice), text(choice), text(field.get("description")))
            for choice in field.get("values") or []
        ]
    return []
