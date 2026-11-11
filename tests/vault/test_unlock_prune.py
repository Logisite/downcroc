from __future__ import annotations

from email.utils import parseaddr
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.seed import until
from tests.vault.support import lock, pruned_events, unlock, vault_path


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def test_archived_account_keeps_credentials_through_unlock(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    bob = stack.accounts[1]

    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")
    lock(stack)
    unlock(stack)

    account = stack.api.get(f"/api/accounts/{bob}")
    assert account["archived_at"] is not None
    assert account["credential_present"] is True
    assert not any(bob in event.get("accounts", []) for event in pruned_events(stack))

    stack.api.post(f"/api/accounts/{bob}/unarchive?confirm=true")
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": bob},
        ),
    )
    _done(stack, batch["id"])

    sent = stack.fakes.sent()
    assert len(sent) == 1
    assert parseaddr(sent[0]["From"])[1] == "bob@local.test"


def test_unlock_prunes_secrets_for_a_deleted_account(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    bob = stack.accounts[1]

    lock(stack)
    status, _ = stack.api.raw("DELETE", f"/api/accounts/{bob}?confirm=true")
    assert status == 200
    unlock(stack)

    pruned = pruned_events(stack)
    assert pruned
    assert bob in pruned[-1]["accounts"]
    assert "app_password" in pruned[-1]["kinds"]
    assert pruned[-1]["count"] >= 1

    listed = {item["id"] for item in stack.api.get("/api/vault")["accounts"]}
    assert bob not in listed


def test_unlock_does_not_rewrite_the_vault_when_nothing_is_pruned(
    stack_factory,
) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    path = Path(vault_path(stack))

    lock(stack)
    before = path.stat().st_mtime_ns
    unlock(stack)

    assert path.stat().st_mtime_ns == before
    assert pruned_events(stack) == []
