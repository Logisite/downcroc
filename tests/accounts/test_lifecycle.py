from __future__ import annotations

from tests.conftest import Stack
from tests.harness.logs import events
from tests.vault.support import set_credential_key


def _create(stack: Stack, account_id: str) -> dict:
    return stack.api.post(
        "/api/jobs",
        {
            "account_id": account_id,
            "recipient": "person@example.com",
            "subject": "Stranded",
            "text": "Body",
        },
    )


def test_archive_strands_work_and_unarchive_restores_watcher(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test", "bob@local.test"])
    _alice, bob = stack.accounts
    job = _create(stack, bob)

    archived = stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")
    assert archived["watcher_enabled"] is False
    assert archived["status"] == "connected"
    assert archived["credential_present"] is True
    assert job["state"] == "queued"

    log = events(stack)["account.archived"][-1]
    assert log["account"] == bob
    assert log["queued_jobs"] >= 1
    assert log["pinned_jobs"] >= 1
    assert log["credential_present"] is True

    capacity = stack.api.get("/api/doctor/capacity")
    assert bob not in capacity["smtp_active"]
    assert bob not in capacity["smtp_queue"]

    restored = stack.api.post(f"/api/accounts/{bob}/unarchive?confirm=true")
    assert restored["watcher_enabled"] is True
    assert restored["status"] == "connected"
    assert restored["credential_present"] is True
    watcher = events(stack)["account.watcher"][-1]
    assert watcher["account"] == bob
    assert watcher["enabled"] is True


def test_unarchive_without_a_credential_stays_disabled(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test", "bob@local.test"])
    alice, bob = stack.accounts
    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")

    set_credential_key(stack, bob, f"{bob}:refresh_token")
    restored = stack.api.post(f"/api/accounts/{bob}/unarchive?confirm=true")

    assert restored["watcher_enabled"] is False
    assert restored["status"] == "needs_reauth"
    assert restored["credential_present"] is False
    log = events(stack)["account.unarchived"][-1]
    assert log["watcher_enabled"] is False
    assert log["credential_present"] is False
    assert stack.api.get(f"/api/accounts/{alice}")["status"] == "connected"
