from __future__ import annotations

from email.utils import parseaddr

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until


def _create(stack: Stack, account_id: str, **overrides) -> dict:
    body = {
        "account_id": account_id,
        "recipient": "person@example.com",
        "subject": "Manual hello",
        "text": "Body",
    }
    body.update(overrides)
    return stack.api.post("/api/jobs", body)


def _sent(stack: Stack, count: int = 1, timeout: float = 30.0) -> list[dict]:
    until(lambda: len(stack.fakes.sent()) >= count, timeout=timeout)
    return stack.fakes.sent()


def test_manual_create_and_send_end_to_end(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]

    status, job = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": alice,
            "recipient": "person@example.com",
            "subject": "Manual hello",
            "text": "Body",
        },
    )
    assert status == 201
    assert job["batch_id"] == "manual"
    assert job["state"] == "queued"
    created = events(stack)["manual.job_created"][-1]
    assert created["job"] == job["id"]
    assert created["account"] == alice
    assert created["batch"] == "manual"

    sent = stack.api.post(f"/api/jobs/{job['id']}/send")
    assert sent["state"] == "sent"

    messages = _sent(stack)
    assert len(messages) == 1
    assert parseaddr(messages[0]["From"])[1] == "alice@local.test"
    assert parseaddr(messages[0]["To"])[1] == "person@example.com"


def test_manual_create_rejects_a_missing_batch(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])

    status, body = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": stack.accounts[0],
            "recipient": "person@example.com",
            "subject": "Manual hello",
            "text": "Body",
            "batch_id": "not-a-batch",
        },
    )
    assert status == 404
    assert body["error"] == "batch_not_found"
    rejected = events(stack)["manual.job_rejected"][-1]
    assert rejected["reason"] == "batch_not_found"
    assert rejected["batch"] == "not-a-batch"


def test_manual_send_rejects_an_archived_account(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test", "bob@local.test"])
    bob = stack.accounts[1]
    job = _create(stack, bob)

    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")
    status, body = stack.api.raw("POST", f"/api/jobs/{job['id']}/send")
    assert status == 409
    assert body["error"] == "account_archived"

    status, body = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": bob,
            "recipient": "other@example.com",
            "subject": "Archived",
            "text": "Body",
        },
    )
    assert status == 409
    assert body["error"] == "account_archived"
    assert stack.fakes.sent() == []


def test_manual_create_rejects_paused_and_pending_accounts(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    stack.api.post(f"/api/accounts/{alice}/pause", {"reason": "maintenance"})

    status, body = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": alice,
            "recipient": "person@example.com",
            "subject": "Paused",
            "text": "Body",
        },
    )
    assert status == 409
    assert body["error"] == "account_unavailable"

    pending = stack.api.create_account("pending@local.test")
    status, body = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": pending["id"],
            "recipient": "person@example.com",
            "subject": "Pending",
            "text": "Body",
        },
    )
    assert status == 409
    assert body["error"] == "account_pending"


def test_batch_import_is_unaffected(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    batch = submit(stack, campaign_of(1, options={"approval": "auto"}))
    until(
        lambda: stack.api.get(f"/api/batches/{batch['id']}")["state"] == "done",
        timeout=60,
    )
    assert len(stack.fakes.sent()) == 1
