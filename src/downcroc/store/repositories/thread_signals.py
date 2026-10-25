from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from downcroc.store.db.models.messages import MessageRow, ThreadRow


@dataclass(frozen=True)
class ThreadSignals:
    reply: bool
    bounce: bool


def thread_signals(session: Session, root_message_ids: list[str]) -> ThreadSignals:
    if not root_message_ids:
        return ThreadSignals(reply=False, bounce=False)
    rows = session.execute(
        select(MessageRow.is_dsn, MessageRow.reply_state)
        .join(ThreadRow, MessageRow.thread_id == ThreadRow.id)
        .where(ThreadRow.root_message_id.in_(root_message_ids))
    ).all()
    reply = any(
        not is_dsn and reply_state in {"confirmed", "probable"}
        for is_dsn, reply_state in rows
    )
    bounce = any(is_dsn for is_dsn, _ in rows)
    return ThreadSignals(reply=reply, bounce=bounce)


def thread_signals_by_root(
    session: Session, root_message_ids: list[str]
) -> dict[str, ThreadSignals]:
    if not root_message_ids:
        return {}
    rows = session.execute(
        select(
            ThreadRow.root_message_id,
            MessageRow.is_dsn,
            MessageRow.reply_state,
        )
        .join(ThreadRow, MessageRow.thread_id == ThreadRow.id)
        .where(ThreadRow.root_message_id.in_(root_message_ids))
    ).all()
    found: dict[str, list[tuple[bool, str]]] = {}
    for root, is_dsn, reply_state in rows:
        found.setdefault(root, []).append((bool(is_dsn), reply_state))
    result: dict[str, ThreadSignals] = {}
    for root, items in found.items():
        result[root] = ThreadSignals(
            reply=any(
                not is_dsn and state in {"confirmed", "probable"}
                for is_dsn, state in items
            ),
            bounce=any(is_dsn for is_dsn, _ in items),
        )
    return result
