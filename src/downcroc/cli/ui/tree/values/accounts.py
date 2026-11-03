from __future__ import annotations

from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import Named, fetch, resolver, text


@resolver(
    "account_id", "account", "reassign_to", "to_account_id", "from_account_id", "to"
)
def accounts(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del state
    archived = path[-1:] == ("unarchive",)
    params = {"archived": "true"} if archived else {}
    rows = fetch(ui, "/api/accounts", **params)
    return [
        Named(text(row.get("id")), _label(row), _detail(row, archived)) for row in rows
    ]


def _label(row: dict) -> str:
    address = text(row.get("address")) or text(row.get("id"))
    label = text(row.get("label"))
    return f"{label} <{address}>" if label else address


def _detail(row: dict, archived: bool) -> str:
    if archived or row.get("archived_at"):
        return "archived"
    parts = [text(row.get("status"))]
    if row.get("paused_at"):
        parts.append("paused")
    return "  ".join(part for part in parts if part)
