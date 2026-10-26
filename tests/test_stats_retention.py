from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.replies import (
    account_address,
    deliver_reply,
    recipient_job,
    sync_and_wait,
)
from tests.harness.seed import until


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _done(stack: Stack, batch_id: str, timeout: float = 90.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def _summary(stack: Stack, account: str | None = None) -> dict:
    day = _today()
    suffix = f"&account_id={account}" if account is not None else ""
    return stack.api.get(f"/api/stats/summary?from={day}&to={day}{suffix}")


def _daily(stack: Stack, account: str | None = None) -> dict:
    day = _today()
    suffix = f"&account_id={account}" if account is not None else ""
    return stack.api.get(f"/api/stats/daily?from={day}&to={day}{suffix}")


def _batches(stack: Stack) -> dict:
    day = _today()
    return stack.api.get(f"/api/stats/batches?from={day}&to={day}")


def _one(rows: list[dict], account: str) -> dict:
    return next(row for row in rows if row["account_id"] == account)


def _send_one(stack: Stack, account: str, key: str = "stats") -> dict:
    batch = submit(
        stack,
        campaign_of(
            1,
            key=key,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        ),
    )
    _done(stack, batch["id"])
    return batch


def _database(stack: Stack) -> sqlite3.Connection:
    return sqlite3.connect(stack.daemon.data_home / "downcroc" / "downcroc.db")


def test_send_and_reply_update_stored_activity(stack_factory) -> None:
    stack = stack_factory(config_extra=dispatch_config(log_level="debug"))
    account = stack.accounts[0]
    batch = submit(
        stack,
        campaign_of(
            2,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        ),
    )
    _done(stack, batch["id"])

    daily = _one(_daily(stack, account)["rows"], account)
    assert daily["sent"] == 2
    assert daily["received"] == 0
    assert daily["replies"] == 0
    assert daily["quota_limit"] == 200

    job = recipient_job(batch, "person1@example.com")
    deliver_reply(
        stack.fakes,
        to_address=account_address(stack, account),
        from_address=job["recipient"],
        subject=job["subject"],
        in_reply_to=job["message_id"],
    )
    sync_and_wait(stack, account, expected=1)

    daily = _one(_daily(stack, account)["rows"], account)
    assert daily["sent"] == 2
    assert daily["received"] == 1
    assert daily["replies"] == 1
    assert daily["bounces"] == 0

    summary = _summary(stack, account)
    assert summary["total"]["sent"] == 2
    assert summary["total"]["received"] == 1
    assert summary["total"]["replies"] == 1
    assert summary["accounts"] == [
        {
            "account_id": account,
            "sent": 2,
            "failed": 0,
            "received": 1,
            "replies": 1,
            "bounces": 0,
            "suppressed": 0,
        }
    ]

    counters = _batches(stack)["rows"][0]
    assert counters["batch_id"] == batch["id"]
    assert counters["sent"] == 2
    assert counters["received"] == 1
    assert counters["replies"] == 1
    assert counters["reply_rate"] == 0.5

    increments = events(stack)["stats.increment"]
    fields = {item["field"] for item in increments}
    assert {"sent", "received", "replies"} <= fields


def test_rebuild_matches_live_and_reports_planted_mismatch(stack_factory) -> None:
    stack = stack_factory()
    account = stack.accounts[0]
    _send_one(stack, account)

    before_summary = _summary(stack)
    before_daily = _daily(stack)
    before_batches = _batches(stack)

    result = stack.api.post("/api/stats/rebuild", {})
    assert result["since"] is None
    assert result["rows"] >= 2

    assert _summary(stack) == before_summary
    assert _daily(stack) == before_daily
    assert _batches(stack) == before_batches

    with closing(_database(stack)) as conn:
        conn.execute(
            "update activity_daily set sent = 99 where account_id = ? and day = ?",
            (account, _today()),
        )
        conn.commit()

    again = stack.api.post("/api/stats/rebuild", {})
    assert again["rows"] >= 2

    invariant = events(stack)["stats.invariant"]
    assert any(
        item["outcome"] == "mismatch" and item["stored"] == 99 and item["rows"] == 1
        for item in invariant
    )
    assert invariant[-1]["outcome"] == "ok"
    assert invariant[-1]["stored"] == 1
    assert _daily(stack) == before_daily

    rebuilt = events(stack)["stats.rebuilt"]
    assert rebuilt[-1]["since"] == "all"
    assert rebuilt[-1]["rows"] >= 2
    assert rebuilt[-1]["duration_ms"] >= 0


def test_pruning_expired_rows_keeps_stored_totals(stack_factory) -> None:
    config = dispatch_config(
        retention_check_s=0.05,
        jobs_days=30,
        mail_days=90,
        hourly_days=1,
    )
    stack = stack_factory(config_extra=config)
    account = stack.accounts[0]
    batch = _send_one(stack, account)
    job = recipient_job(batch, "person1@example.com")
    deliver_reply(
        stack.fakes,
        to_address=account_address(stack, account),
        from_address=job["recipient"],
        subject=job["subject"],
        in_reply_to=job["message_id"],
    )
    messages = sync_and_wait(stack, account, expected=1)

    before_summary = _summary(stack)
    before_batches = _batches(stack)

    old_job = (datetime.now(UTC) - timedelta(days=40)).isoformat(
        timespec="milliseconds"
    )
    old_mail = (datetime.now(UTC) - timedelta(days=100)).isoformat(
        timespec="milliseconds"
    )
    with closing(_database(stack)) as conn:
        conn.execute(
            "update jobs set sent_at = ?, updated_at = ? where id = ?",
            (old_job, old_job, job["id"]),
        )
        conn.execute(
            "update messages set ingested_at = ? where id = ?",
            (old_mail, messages[0]["id"]),
        )
        hours = conn.execute(
            "select rowid from activity_hourly where account_id = ?",
            (account,),
        ).fetchall()
        for index, (rowid,) in enumerate(hours):
            stamp = (
                datetime.now().astimezone() - timedelta(days=2, hours=index)
            ).strftime("%Y-%m-%dT%H:00:00")
            conn.execute(
                "update activity_hourly set hour_start = ? where rowid = ?",
                (stamp, rowid),
            )
        conn.commit()

    until(
        lambda: (
            {"jobs", "messages", "activity_hourly"}
            <= {
                item["table"]
                for item in events(stack).get("retention.pruned", [])
                if item["count"] > 0
            }
        ),
        timeout=30.0,
    )

    assert stack.api.get(f"/api/jobs?batch={batch['id']}") == []
    assert stack.api.get(f"/api/messages?account={account}") == []
    assert _summary(stack) == before_summary
    assert _batches(stack) == before_batches

    rebuilt = stack.api.post("/api/stats/rebuild", {})
    assert rebuilt["since"] is None
    assert _summary(stack) == before_summary
    assert _batches(stack) == before_batches

    pruned = events(stack)["retention.pruned"]
    jobs = next(item for item in pruned if item["table"] == "jobs")
    mail = next(item for item in pruned if item["table"] == "messages")
    hourly = next(item for item in pruned if item["table"] == "activity_hourly")
    assert jobs["count"] == 1
    assert jobs["bytes"] > 0
    assert mail["count"] == 1
    assert mail["bytes"] > 0
    assert hourly["count"] == len(hours)


def test_summaries_split_accounts_and_total(stack_factory) -> None:
    stack = stack_factory()
    alice, bob = stack.accounts

    _send_one(stack, alice, key="alice")
    _send_one(stack, bob, key="bob")

    summary = _summary(stack)
    assert summary["total"]["sent"] == 2
    assert len(summary["accounts"]) == 2
    assert _one(summary["accounts"], alice)["sent"] == 1
    assert _one(summary["accounts"], bob)["sent"] == 1

    only_alice = _summary(stack, alice)
    assert only_alice["total"]["sent"] == 1
    assert [row["account_id"] for row in only_alice["accounts"]] == [alice]

    accounts = stack.api.get(f"/api/stats/accounts?from={_today()}&to={_today()}")[
        "rows"
    ]
    assert len(accounts) == 2
    assert {row["address"] for row in accounts} == {
        "alice@local.test",
        "bob@local.test",
    }
    assert all(row["remaining_allowance"] == 199 for row in accounts)

    only = stack.api.get(
        f"/api/stats/accounts?from={_today()}&to={_today()}&account_id={alice}"
    )["rows"]
    assert [row["account_id"] for row in only] == [alice]

    daily = _daily(stack)["rows"]
    assert len(daily) == 2
    assert _one(daily, alice)["sent"] == 1
    assert _one(daily, bob)["sent"] == 1

    batches = _batches(stack)["rows"]
    assert len(batches) == 2
    assert all(row["sent"] == 1 for row in batches)
