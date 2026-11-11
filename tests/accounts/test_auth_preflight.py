from __future__ import annotations

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until
from tests.vault.support import lock, set_credential_key, unlock

HOLD = {"not_before": "2999-01-01T00:00:00Z"}


def _account(stack: Stack, account_id: str) -> dict:
    return stack.api.get(f"/api/accounts/{account_id}")


def _wait_auth(stack: Stack, account_id: str, status: str) -> dict:
    until(
        lambda: _account(stack, account_id).get("auth_status") == status,
        timeout=30,
    )
    return _account(stack, account_id)


def test_unlock_runs_the_auth_preflight(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]

    lock(stack)
    unlock(stack)

    account = _wait_auth(stack, alice, "ok")
    assert account["auth_action"] is None
    assert account["auth_checked_at"] is not None
    assert stack.fakes.sent() == []

    vault_account = next(
        item for item in stack.api.get("/api/vault")["accounts"] if item["id"] == alice
    )
    assert vault_account["auth_status"] == "ok"

    found = events(stack)
    assert found["account.auth_check_start"]
    assert found["account.auth_check_ok"]
    summary = found["account.auth_check_summary"][-1]
    assert summary["checked"] >= 1
    assert summary["ok"] >= 1


def test_missing_credential_marks_needs_reauth(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]

    set_credential_key(stack, alice, f"{alice}:refresh_token")
    lock(stack)
    unlock(stack)

    account = _wait_auth(stack, alice, "needs_reauth")
    assert account["status"] == "needs_reauth"
    assert account["auth_error"] == "credential_missing"
    assert account["auth_action"] == "reconnect"


def test_rejected_credential_marks_needs_reauth(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    stack.fakes.reject_login("alice@local.test")

    lock(stack)
    unlock(stack)

    account = _wait_auth(stack, alice, "needs_reauth")
    assert account["status"] == "needs_reauth"
    assert account["auth_error"] == "imap_auth_failed"
    assert account["auth_action"] == "reconnect"


def test_provider_unavailable_is_not_reauth(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    stack.fakes.stop()

    lock(stack)
    unlock(stack)

    account = _wait_auth(stack, alice, "unavailable")
    assert account["status"] == "connected"
    assert account["auth_error"] == "imap_unreachable"
    assert account["auth_action"] == "retry"


def test_eta_has_basis_and_refreshes_after_a_policy_change(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    batch = submit(
        stack,
        campaign_of(5, options={"approval": "auto", **HOLD}),
    )
    first = stack.api.get(f"/api/batches/{batch['id']}")["eta"]
    assert first["as_of"]
    assert first["basis"]

    status, _ = stack.api.raw(
        "PUT",
        "/api/sending",
        {"jitter_min": 120, "jitter_max": 120},
    )
    assert status == 200

    second = stack.api.get(f"/api/batches/{batch['id']}")["eta"]
    assert second["as_of"] >= first["as_of"]
    assert second["basis"]
    assert second["duration_s"]["max"] > first["duration_s"]["max"]

    job = stack.api.get(f"/api/jobs/{batch['recipients'][0]['id']}")
    assert job["eta"]["as_of"]
    assert job["eta"]["basis"]

    pending = stack.api.get("/api/stats/pending")
    assert pending["as_of"]
    assert pending["basis"]
