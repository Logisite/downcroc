from __future__ import annotations

import time

from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import write_json
from tests.vault.support import lock, set_credential_key, set_status, unlock


def test_unlock_marks_a_missing_credential(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    alice, bob = stack.accounts

    set_credential_key(stack, bob, f"{bob}:refresh_token")
    listed = {item["id"]: item for item in stack.api.get("/api/accounts")}
    assert listed[bob]["credential_present"] is False
    assert listed[alice]["credential_present"] is True

    lock(stack)
    unlock(stack)

    account = stack.api.get(f"/api/accounts/{bob}")
    assert account["status"] == "needs_reauth"
    assert account["credential_present"] is False

    vault_accounts = {
        item["id"]: item for item in stack.api.get("/api/vault")["accounts"]
    }
    assert vault_accounts[bob]["credential_present"] is False
    assert vault_accounts[alice]["credential_present"] is True

    missing = events(stack)["account.credential_missing"][-1]
    assert missing["account"] == bob
    assert missing["kind"] == "refresh_token"
    assert missing["action"] == "needs_reauth"


def test_routing_and_dispatch_skip_a_missing_credential(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(tick_s=0.05, jitter_max=0),
        accounts=["alice@local.test", "bob@local.test"],
    )
    _alice, bob = stack.accounts

    stack.api.post("/api/service/pause", {"reason": "test"})
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": bob},
        ),
    )
    job_id = batch["recipients"][0]["id"]

    set_credential_key(stack, bob, f"{bob}:refresh_token")
    lock(stack)
    unlock(stack)
    set_status(stack, bob, "connected")

    rejected = write_json(
        input_files(stack),
        "missing-credential.json",
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": bob},
        ),
    )
    status, body = stack.api.raw(
        "POST",
        "/api/batches",
        {"path": str(rejected), "template": None, "key": None},
    )
    assert status == 409
    assert body["error"] == "account_unavailable"

    stack.api.post("/api/service/resume", {})
    time.sleep(1.0)

    assert stack.fakes.sent() == []
    assert stack.api.get(f"/api/jobs/{job_id}")["state"] == "queued"
    quota = stack.api.get(f"/api/accounts/{bob}")["quota"]
    assert quota["used"] == 0
    assert quota["reserved"] == 0
    assert quota["available"] == quota["daily_allowance"]
