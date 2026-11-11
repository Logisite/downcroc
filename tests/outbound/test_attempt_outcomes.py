from __future__ import annotations

import sqlite3
from contextlib import closing

from downcroc.runtime.clock import utc_now
from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until


def _create(stack: Stack, account_id: str) -> dict:
    return stack.api.post(
        "/api/jobs",
        {
            "account_id": account_id,
            "recipient": "person@example.com",
            "subject": "Attempt",
            "text": "Body",
        },
    )


def _database(stack: Stack) -> str:
    return str(stack.daemon.data_home / "downcroc" / "downcroc.db")


def test_reauth_finalizes_the_reserved_attempt(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    job = _create(stack, alice)
    stack.fakes.reject_smtp_auth()

    status, body = stack.api.raw("POST", f"/api/jobs/{job['id']}/send")
    assert status == 409
    assert body["error"] == "account_needs_reauth"

    attempts = stack.api.get(f"/api/jobs/{job['id']}/attempts")
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["outcome"] == "failed"
    assert attempt["finished_at"] is not None
    assert attempt["transport"] == "smtp"
    assert attempt["error_code"] == "smtp_535"

    assert events(stack)["job.blocked"][-1]["retryable"] is False
    released = events(stack)["quota.released"][-1]
    assert released["job"] == job["id"]
    assert released["attempt"] == attempt["id"]


def test_startup_reconciliation_closes_stale_attempts(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    job = _create(stack, alice)
    attempt_id = "att_stale"
    with closing(sqlite3.connect(_database(stack), timeout=10)) as connection:
        connection.execute(
            "insert into send_attempts "
            "(id, job_id, account_id, binding_id, transport, started_at, "
            "finished_at, outcome, accepted, error_code, error_message, "
            "provider_message_id, detail, quota_day, quota_state) "
            "values (?, ?, ?, null, 'pending', ?, null, 'reserved', null, "
            "null, null, null, null, ?, 'reserved')",
            (attempt_id, job["id"], alice, utc_now(), utc_now()[:10]),
        )
        connection.commit()

    stack.daemon.stop()
    stack.daemon.start(stack.fakes, preserve_config=True)
    stack.api.unlock()

    attempts = stack.api.get(f"/api/jobs/{job['id']}/attempts")
    stale = next(item for item in attempts if item["id"] == attempt_id)
    assert stale["outcome"] == "interrupted"
    assert stale["finished_at"] is not None
    assert events(stack)["send_attempts.reconciled"][-1]["count"] >= 1


def test_dispatch_logs_non_retryable_errors_at_warning(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(tick_s=0.05),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    stack.fakes.reject_smtp_auth()
    submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": alice},
        ),
    )

    until(lambda: bool(events(stack).get("dispatch.error")), timeout=30)
    error = events(stack)["dispatch.error"][-1]
    assert error["level"] == "warning"
    assert error["account"] == alice
    assert error["code"] == "account_needs_reauth"
    assert error["job"]
