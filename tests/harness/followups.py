from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from email.message import Message

from tests.conftest import Stack
from tests.harness.replies import (
    account_address,
    deliver_reply,
    recipient_job,
    sync_and_wait,
)
from tests.harness.seed import until


def done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def batches(stack: Stack, parent_id: str) -> list[dict]:
    found = stack.api.get("/api/batches?limit=500")
    return [
        batch
        for batch in found
        if batch["kind"] == "follow_up" and batch["parent_batch_id"] == parent_id
    ]


def step(stack: Stack, parent_id: str, step_key: str, timeout: float = 60.0) -> dict:
    def find() -> dict | None:
        for batch in batches(stack, parent_id):
            if batch["options"].get("step") == step_key:
                return stack.api.get(f"/api/batches/{batch['id']}")
        return None

    until(lambda: find() is not None, timeout=timeout)
    found = find()
    assert found is not None
    return found


def job(batch: dict, recipient: str) -> dict:
    return next(item for item in batch["recipients"] if item["recipient"] == recipient)


def wait_state(
    stack: Stack, batch_id: str, recipient: str, state: str, timeout: float = 60.0
) -> dict:
    def find() -> dict | None:
        batch = stack.api.get(f"/api/batches/{batch_id}")
        item = job(batch, recipient)
        return item if item["state"] == state else None

    until(lambda: find() is not None, timeout=timeout)
    found = find()
    assert found is not None
    return found


def age_jobs(stack: Stack, job_ids: list[str], days: int) -> None:
    path = stack.daemon.data_home / "downcroc" / "downcroc.db"
    stamp = (
        (datetime.now(UTC) - timedelta(days=days))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    with closing(sqlite3.connect(path, timeout=10)) as database:
        for job_id in job_ids:
            database.execute(
                "update jobs set sent_at = ? where id = ?", (stamp, job_id)
            )
        database.commit()


def sent(stack: Stack, message_id: str) -> Message:
    wanted = message_id.strip("<>")
    for item in stack.fakes.sent():
        if (item.get("Message-ID") or "").strip("<>") == wanted:
            return item
    raise AssertionError(f"message {message_id} was not sent")


def ids(message: Message, header: str) -> list[str]:
    return [item.strip("<>") for item in (message.get(header) or "").split()]


def body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                text = (part.get_payload(decode=True) or b"").decode()
                break
        else:
            return ""
    else:
        text = (message.get_payload(decode=True) or b"").decode()
    return text.replace("\r\n", "\n").strip()


def counts(stack: Stack, batch_id: str) -> dict[str, int]:
    return stack.api.get(f"/api/batches/{batch_id}")["counts"]


def reply(
    stack: Stack,
    account_id: str,
    *,
    from_address: str,
    subject: str,
    in_reply_to: str,
    references: tuple[str, ...],
    expected: int,
) -> None:
    deliver_reply(
        stack.fakes,
        to_address=account_address(stack, account_id),
        from_address=from_address,
        subject=subject,
        in_reply_to=in_reply_to,
        references=references,
    )
    sync_and_wait(stack, account_id, expected)


__all__ = [
    "age_jobs",
    "batches",
    "body",
    "counts",
    "done",
    "ids",
    "job",
    "recipient_job",
    "reply",
    "sent",
    "step",
    "wait_state",
]
