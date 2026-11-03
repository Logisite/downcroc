from __future__ import annotations

from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import (
    Named,
    fetch,
    fetch_one,
    resolver,
    text,
)


@resolver("message_id")
def messages(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path, state
    rows = fetch(ui, "/api/messages", limit=50)
    return [
        Named(
            text(row.get("id")),
            text(row.get("subject")) or text(row.get("id")),
            f"{text(row.get('from_address'))}  {text(row.get('date'))}",
        )
        for row in rows
    ]


@resolver("thread_id")
def threads(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path, state
    rows = fetch(ui, "/api/threads", limit=50)
    return [
        Named(
            text(row.get("id")),
            text(row.get("subject")) or text(row.get("id")),
            f"{text(row.get('message_count'))} messages",
        )
        for row in rows
    ]


@resolver("attachment_id")
def attachments(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path
    message_id = state.get("message_id")
    if not message_id:
        return []
    row = fetch_one(ui, f"/api/messages/{message_id}")
    return [
        Named(
            text(item.get("id")),
            text(item.get("filename")) or text(item.get("id")),
            f"{text(item.get('content_type'))}  {text(item.get('size'))} bytes",
        )
        for item in row.get("attachments") or []
    ]
