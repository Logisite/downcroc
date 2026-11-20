from __future__ import annotations

import json
from datetime import UTC, datetime

from tests.harness.campaigns import campaign_of, submit
from tests.harness.inbound import cli
from tests.harness.replies import account_address
from tests.harness.seed import until


def _send(stack, account: str) -> None:
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        ),
    )
    until(
        lambda: stack.api.get(f"/api/batches/{batch['id']}")["state"] == "done",
        timeout=90.0,
    )


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def test_addresses_flag_shows_addresses_in_stats(stack_factory) -> None:
    """--addresses resolves account ids to addresses in human-readable output."""
    stack = stack_factory(accounts=["alice@local.test"])
    account = stack.accounts[0]
    address = account_address(stack, account)
    _send(stack, account)

    base = ["stats", "accounts", "--from", _today(), "--to", _today()]
    plain = cli(stack, *base)
    assert plain.returncode == 0, plain.stderr
    assert account in plain.stdout

    resolved = cli(stack, *base, "--addresses")
    assert resolved.returncode == 0, resolved.stderr
    assert address in resolved.stdout
    assert account not in resolved.stdout


def test_addresses_flag_before_command(stack_factory, monkeypatch) -> None:
    """--addresses is honored when placed before the command."""
    monkeypatch.setenv("COLUMNS", "200")
    stack = stack_factory(accounts=["alice@local.test"])
    account = stack.accounts[0]
    address = account_address(stack, account)
    _send(stack, account)

    result = cli(
        stack,
        "--addresses",
        "stats",
        "accounts",
        "--from",
        _today(),
        "--to",
        _today(),
    )
    assert result.returncode == 0, result.stderr
    assert address in result.stdout
    assert account not in result.stdout


def test_addresses_flag_keeps_ids_in_json(stack_factory) -> None:
    """--addresses does not change machine-readable output."""
    stack = stack_factory(accounts=["alice@local.test"])
    account = stack.accounts[0]
    _send(stack, account)

    result = cli(
        stack,
        "stats",
        "accounts",
        "--from",
        _today(),
        "--to",
        _today(),
        "--addresses",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    ids = [row["account_id"] for row in body.get("rows", [])]
    assert account in ids


def test_addresses_flag_is_global(stack_factory) -> None:
    """--addresses is accepted on every command (global common flag)."""
    stack = stack_factory(accounts=[])
    for args in (
        ["job", "list"],
        ["backfill", "status"],
        ["failed", "list"],
        ["stats", "summary"],
    ):
        result = cli(stack, *args, "--addresses", "--json")
        assert result.returncode == 0, (args, result.stderr)
