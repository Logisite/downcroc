from __future__ import annotations

from tests.harness.dispatch import dispatch_config


def test_sticky_smtp_seat_is_configurable_and_stable(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )

    first = stack.api.get("/api/doctor/capacity")
    assert len(first["smtp_active"]) == 1
    assert first["pinned_overflow"] == 0
    second = stack.api.get("/api/doctor/capacity")
    assert second["smtp_active"] == first["smtp_active"]

    status, body = stack.api.raw(
        "PATCH",
        "/api/config",
        {"dispatch": {"smtp_seat_sticky": False, "smtp_seat_max_s": 30}},
    )
    assert status == 200, body
    values = stack.api.get("/api/config")["config"]["dispatch"]
    assert values["smtp_seat_sticky"] is False
    assert values["smtp_seat_max_s"] == 30


def test_archived_accounts_do_not_hold_a_seat(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    alice, bob = stack.accounts
    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")

    plan = stack.api.get("/api/doctor/capacity")
    assert bob not in plan["smtp_active"]
    assert bob not in plan["smtp_queue"]
    assert alice in plan["smtp_queue"]
