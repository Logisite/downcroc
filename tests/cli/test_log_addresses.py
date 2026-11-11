from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack

ROOT = Path(__file__).resolve().parents[2]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_logs_show_ids_by_default_and_addresses_on_request(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]

    plain = _cli(stack, "logs", "--event", "account.connected", "--limit", "1")
    assert plain.returncode == 0, plain.stderr
    assert alice in plain.stdout

    shown = _cli(
        stack,
        "logs",
        "--event",
        "account.connected",
        "--addresses",
        "--limit",
        "1",
    )
    assert shown.returncode == 0, shown.stderr
    assert "alice@local.test" in shown.stdout
    assert alice not in shown.stdout

    machine = _cli(
        stack,
        "logs",
        "--event",
        "account.connected",
        "--addresses",
        "--json",
        "--limit",
        "1",
    )
    assert machine.returncode == 0, machine.stderr
    entry = json.loads(machine.stdout)
    assert entry["account"] == alice
    assert entry["account_address"] == "alice@local.test"


def test_logs_filter_by_address_and_archived_account(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test", "bob@local.test"])
    _alice, bob = stack.accounts
    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")

    filtered = _cli(
        stack,
        "logs",
        "--addresses",
        "--account",
        "alice@local.test",
        "--event",
        "account.connected",
        "--limit",
        "10",
    )
    assert filtered.returncode == 0, filtered.stderr
    assert "alice@local.test" in filtered.stdout
    assert bob not in filtered.stdout

    archived = _cli(
        stack,
        "logs",
        "--addresses",
        "--account",
        "bob@local.test",
        "--event",
        "account.archived",
        "--limit",
        "1",
    )
    assert archived.returncode == 0, archived.stderr
    assert "bob@local.test" in archived.stdout


def test_logs_fall_back_to_ids_when_the_daemon_is_down(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    stack.daemon.stop()

    result = _cli(
        stack,
        "logs",
        "--addresses",
        "--event",
        "account.connected",
        "--limit",
        "1",
    )
    assert result.returncode == 0
    assert "warning: account addresses unavailable" in result.stderr
    assert alice in result.stdout
