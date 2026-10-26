from __future__ import annotations

import os
import signal
from datetime import datetime, timedelta

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.replies import (
    account_address,
    at_offset,
    deliver_dsn,
    deliver_reply,
    messages,
    recipient_job,
    sync_and_wait,
)
from tests.harness.seed import until


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def _by_header(stack: Stack, account_id: str, header: str) -> dict:
    found = [
        item
        for item in messages(stack, account_id)
        if (item["message_id"] or "") == header
    ]
    assert len(found) == 1
    return found[0]


def _counts(stack: Stack, batch_id: str) -> dict[str, int]:
    return stack.api.get(f"/api/batches/{batch_id}")["counts"]


def test_confirmed_replies_count_once_and_survive_restart(stack_factory) -> None:
    config = dispatch_config()
    stack = stack_factory(
        accounts=["alice@local.test"],
        config_extra=config,
    )
    account = stack.accounts[0]
    to_address = account_address(stack, account)
    document = campaign_of(
        2,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
    )
    batch = submit(stack, document, "replies.json")
    _done(stack, batch["id"])
    job = recipient_job(batch, "person1@example.com")

    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        message_id="reply-one@example.com",
        in_reply_to=job["message_id"],
        references=(job["message_id"],),
    )
    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        message_id="reply-two@example.com",
        in_reply_to=job["message_id"],
        references=(job["message_id"],),
    )
    found = sync_and_wait(stack, account, 2)

    assert {item["message_id"] for item in found} == {
        "reply-one@example.com",
        "reply-two@example.com",
    }
    assert all(item["reply_state"] == "confirmed" for item in found)
    assert all(item["job_id"] == job["id"] for item in found)
    assert all(item["is_dsn"] is False for item in found)
    thread_id = found[0]["thread_id"]
    assert all(item["thread_id"] == thread_id for item in found)

    thread = stack.api.get(f"/api/threads/{thread_id}")["thread"]
    assert thread["batch_id"] == batch["id"]
    assert thread["message_count"] == 2
    assert thread["reply_count"] == 2
    counts = _counts(stack, batch["id"])
    assert counts == {
        "sent": 2,
        "inbound": 2,
        "replies": 2,
        "late_replies": 0,
        "bounces": 0,
    }
    rows = stack.api.get(f"/api/messages?thread={thread_id}&limit=500")
    assert len(rows) == counts["inbound"]
    assert (
        sum(1 for row in rows if row["reply_state"] == "confirmed") == counts["replies"]
    )

    logged = events(stack)
    assert any(
        item["kind"] == "reply"
        and item["confidence"] == "confirmed"
        and "in-reply-to" in item["headers"]
        for item in logged["message.classified"]
    )
    assert any(
        item["thread"] == thread_id and item["method"] == "in-reply-to"
        for item in logged["thread.linked"]
    )
    added = [
        item
        for item in logged["suppression.added"]
        if item["address"] == "person1@example.com"
    ]
    assert len(added) == 1
    assert added[0]["reason"] == "confirmed_reply"

    second = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "review"},
            routing={
                "mode": "fixed",
                "account": account,
            },
        )
        | {
            "messages": [
                {
                    "to": {"email": "person1@example.com"},
                    "subject": "Again",
                    "text": "Body",
                }
            ]
        },
        "second.json",
    )
    preview = stack.api.get(f"/api/batches/{second['id']}/suppression-preview")
    assert preview == [
        {
            "address": "person1@example.com",
            "account_id": account,
            "reason": "confirmed_reply",
        }
    ]

    os.kill(stack.daemon.process.pid, signal.SIGKILL)
    stack.daemon.process.wait(timeout=10)
    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()

    assert _counts(stack, batch["id"]) == {
        "sent": 2,
        "inbound": 2,
        "replies": 2,
        "late_replies": 0,
        "bounces": 0,
    }
    assert len(messages(stack, account)) == 2


def test_dsn_is_a_bounce_not_a_reply(stack_factory) -> None:
    stack = stack_factory(
        accounts=["alice@local.test"],
        config_extra=dispatch_config(),
    )
    account = stack.accounts[0]
    to_address = account_address(stack, account)
    batch = submit(
        stack,
        campaign_of(1, options={"approval": "auto"}),
        "bounce.json",
    )
    _done(stack, batch["id"])
    job = recipient_job(batch, "person1@example.com")

    deliver_dsn(
        stack.fakes,
        to_address=to_address,
        recipient="person1@example.com",
        original_message_id=job["message_id"],
        status="5.1.1",
        action="failed",
    )
    found = sync_and_wait(stack, account, 1)
    assert len(found) == 1
    dsn = found[0]
    assert dsn["is_dsn"] is True
    assert dsn["reply_state"] == "none"
    assert dsn["job_id"] == job["id"]
    assert _counts(stack, batch["id"]) == {
        "sent": 1,
        "inbound": 1,
        "replies": 0,
        "late_replies": 0,
        "bounces": 1,
    }

    until(lambda: len(events(stack).get("dsn.parsed", [])) >= 1)
    parsed = events(stack)["dsn.parsed"]
    assert len(parsed) == 1
    assert parsed[0]["job"] == job["id"]
    assert parsed[0]["status"] == "failed"
    assert parsed[0]["code"] == "5.1.1"

    deliver_dsn(
        stack.fakes,
        to_address=to_address,
        recipient="person1@example.com",
    )
    found = sync_and_wait(stack, account, 2)
    dsns = [item for item in found if item["is_dsn"]]
    assert len(dsns) == 2
    assert all(item["job_id"] == job["id"] for item in dsns)
    until(lambda: len(events(stack).get("dsn.parsed", [])) >= 2)
    parsed = events(stack)["dsn.parsed"]
    assert len(parsed) == 2
    assert all(item["job"] == job["id"] for item in parsed)

    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        message_id="after-bounce@example.com",
        in_reply_to=job["message_id"],
    )
    sync_and_wait(stack, account, 3)
    assert _counts(stack, batch["id"]) == {
        "sent": 1,
        "inbound": 3,
        "replies": 1,
        "late_replies": 0,
        "bounces": 2,
    }


def test_probable_fallback_and_late_replies_stay_separate(stack_factory) -> None:
    stack = stack_factory(
        accounts=["alice@local.test"],
        config_extra=dispatch_config(),
    )
    account = stack.accounts[0]
    to_address = account_address(stack, account)
    document = campaign_of(
        1,
        options={"approval": "auto", "reply_window_days": 30},
    )
    document["messages"][0]["subject"] = "Quarterly update"
    document["messages"][0]["to"] = {"email": "person1@example.com"}
    batch = submit(stack, document, "fallback.json")
    _done(stack, batch["id"])
    job = recipient_job(batch, "person1@example.com")

    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Quarterly update",
        message_id="probable@example.com",
    )
    sync_and_wait(stack, account, 1)
    probable = _by_header(stack, account, "probable@example.com")
    assert probable["reply_state"] == "probable"
    assert probable["job_id"] is None
    thread = stack.api.get(f"/api/threads/{probable['thread_id']}")["thread"]
    assert thread["batch_id"] == batch["id"]
    assert _counts(stack, batch["id"]) == {
        "sent": 1,
        "inbound": 1,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    logged = events(stack)
    assert any(
        item["message_id"] == probable["id"] and item["confirmed"] is False
        for item in logged["reply.attributed"]
    )
    assert any(
        item["message_id"] == probable["id"]
        and item["kind"] == "reply"
        and item["confidence"] == "probable"
        and "subject" in item["headers"]
        for item in logged["message.classified"]
    )
    assert any(
        item["message_id"] == probable["id"] and item["method"] == "subject"
        for item in logged["thread.linked"]
    )

    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Quarterly update",
        message_id="late@example.com",
        in_reply_to=job["message_id"],
        date=datetime.now().astimezone() + timedelta(days=200),
    )
    sync_and_wait(stack, account, 2)
    late = _by_header(stack, account, "late@example.com")
    assert late["reply_state"] == "confirmed"
    assert _counts(stack, batch["id"]) == {
        "sent": 1,
        "inbound": 2,
        "replies": 1,
        "late_replies": 1,
        "bounces": 0,
    }
    assert (
        len(
            [
                item
                for item in events(stack)["suppression.added"]
                if item["address"] == "person1@example.com"
            ]
        )
        == 1
    )

    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="stranger@example.com",
        subject="Re: Something else",
        message_id="orphan@example.com",
        in_reply_to="missing@example.com",
        date=at_offset(0),
    )
    sync_and_wait(stack, account, 3)
    orphan = _by_header(stack, account, "orphan@example.com")
    assert orphan["reply_state"] == "none"
    assert orphan["job_id"] is None
    orphan_thread = stack.api.get(f"/api/threads/{orphan['thread_id']}")["thread"]
    assert orphan_thread["batch_id"] is None
    assert _counts(stack, batch["id"]) == {
        "sent": 1,
        "inbound": 2,
        "replies": 1,
        "late_replies": 1,
        "bounces": 0,
    }
    unattributed = events(stack)["reply.unattributed"]
    assert any(
        item["message_id"] == orphan["id"] and item["reason"] == "unknown_thread"
        for item in unattributed
    )
