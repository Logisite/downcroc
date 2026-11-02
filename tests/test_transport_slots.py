from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.dispatch import dispatch_config

ROOT = Path(__file__).resolve().parents[1]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _json(stack: Stack, *args: str) -> dict | list:
    result = _cli(stack, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _slots(stack: Stack) -> dict[str, str]:
    slots: dict[str, str] = {}
    for account_id in stack.accounts:
        bindings = _json(stack, "account", "transport", "list", account_id, "--json")
        smtp = [item for item in bindings if item["kind"] == "smtp"]
        assert len(smtp) == 1
        slots[account_id] = smtp[0]["slot"]
    return slots


def test_cli_transport_list_follows_live_smtp_seats(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )

    plan = _json(stack, "doctor", "capacity", "--json")
    assert len(plan["smtp_active"]) == 1
    assert len(plan["smtp_waiting"]) == 1

    changed = _json(
        stack,
        "config",
        "set",
        "dispatch.smtp_seats",
        "2",
        "--json",
    )
    assert "dispatch.smtp_seats" in changed["changed"]

    plan = _json(stack, "doctor", "capacity", "--json")
    assert len(plan["smtp_active"]) == 2
    assert plan["smtp_waiting"] == []
    assert set(_slots(stack).values()) == {"active"}


def test_cli_doctor_capacity_reports_the_slot_plan(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )

    body = _json(stack, "doctor", "capacity", "--json")

    assert body["configured_smtp_seats"] == 1
    assert len(body["smtp_active"]) == 1
    assert len(body["smtp_queue"]) == 2
    assert len(body["smtp_waiting"]) == 1
    assert body["password_accounts"] == 2
    assert body["oauth_accounts"] == 0
