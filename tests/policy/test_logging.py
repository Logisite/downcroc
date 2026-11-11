from __future__ import annotations

from tests.harness.logs import events


def test_policy_change_logs_values_and_resolution(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]

    before = stack.api.get("/api/sending")["values"]["daily_allowance"]
    target = before + 23
    status, _ = stack.api.raw(
        "PUT",
        "/api/sending",
        {"daily_allowance": target},
    )
    assert status == 200
    changed = events(stack)["policy.changed"][-1]
    assert changed["old"]["daily_allowance"] == before
    assert changed["new"]["daily_allowance"] == target
    resolved = events(stack)["policy.resolved"][-1]
    assert resolved["account"] == "service"
    assert resolved["limit"] == target
    assert resolved["previous"] == before

    status, _ = stack.api.raw(
        "PUT",
        f"/api/accounts/{alice}/policy",
        {"daily_allowance": target + 5},
    )
    assert status == 200
    status, _ = stack.api.raw("DELETE", f"/api/accounts/{alice}/policy")
    assert status == 200
    cleared = events(stack)["policy.cleared"][-1]
    assert cleared["scope"] == alice
    assert cleared["previous"]["daily_allowance"] == target + 5
    assert cleared["resolved"]["daily_allowance"] == target


def test_vault_and_service_events_carry_state(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])

    vault = events(stack)["vault.saved"][-1]
    assert vault["state"] == "unlocked"
    assert vault["bytes"] > 0

    stack.api.post("/api/service/pause", {"reason": "maintenance"})
    paused = events(stack)["service.paused"][-1]
    assert paused["actor"] == "api"
    assert paused["reason"] == "maintenance"

    stack.api.post("/api/service/resume", {})


def test_policy_view_and_events_stay_consistent(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]

    view = stack.api.get(f"/api/accounts/{alice}/policy")
    before = view["values"]["daily_allowance"]
    status, updated = stack.api.raw(
        "PUT",
        f"/api/accounts/{alice}/policy",
        {"daily_allowance": before + 7},
    )
    assert status == 200
    assert updated["values"]["daily_allowance"] == before + 7
    event = events(stack)["policy.changed"][-1]
    assert event["new"]["daily_allowance"] == before + 7
    assert event["old"]["daily_allowance"] == before
