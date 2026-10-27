from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, input_files
from tests.harness.seed import write_json

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


def test_cli_reads_daemon_state(stack_factory) -> None:
    stack = stack_factory()

    vault = _json(stack, "vault", "status", "--json")
    assert vault["state"] == "unlocked"

    accounts = _json(stack, "account", "list", "--json")
    assert len(accounts) == 2
    assert {item["id"] for item in accounts} == set(stack.accounts)

    account = _json(stack, "account", "show", stack.accounts[0], "--json")
    assert account["status"] == "connected"

    config = _json(stack, "config", "show", "--json")
    assert "sending" in config["config"]

    summary = _json(stack, "stats", "summary", "--json")
    assert summary["total"]["sent"] == 0

    assert _json(stack, "failed", "list", "--json") == []
    assert _json(stack, "mail", "list", "--json") == []
    assert _json(stack, "mail", "threads", "--json") == []

    service = _json(stack, "service", "status", "--json")
    assert service["state"] == "running"


def test_cli_manages_accounts(stack_factory) -> None:
    stack = stack_factory()

    created = _json(
        stack,
        "account",
        "add",
        "--provider",
        "generic",
        "--address",
        "third@local.test",
        "--label",
        "Third",
        "--json",
    )
    assert created["status"] == "pending"
    assert created["label"] == "Third"

    accounts = _json(stack, "account", "list", "--json")
    assert len(accounts) == 3

    shown = _json(stack, "account", "show", created["id"], "--json")
    assert shown["address"] == "third@local.test"

    removed = _cli(stack, "account", "delete", created["id"], "--yes")
    assert removed.returncode == 0, removed.stderr
    assert len(_json(stack, "account", "list", "--json")) == 2


def test_cli_sets_config_and_writes_directory_backup(
    stack_factory,
    tmp_path: Path,
) -> None:
    stack = stack_factory()

    changed = _json(
        stack,
        "config",
        "set",
        "sending.jitter_min",
        "1",
        "--json",
    )
    assert "sending.jitter_min" in changed["changed"]

    bundles = tmp_path / "bundles"
    bundles.mkdir()
    result = _cli(stack, "backup", str(bundles))
    assert result.returncode == 0, result.stderr
    created = list(bundles.glob("downcroc-*.tar.zst"))
    assert len(created) == 1
    assert created[0].stat().st_size > 0


def test_cli_previews_submits_and_cancels_batch(stack_factory) -> None:
    stack = stack_factory()
    path = write_json(
        input_files(stack),
        "cli-campaign.json",
        campaign_of(2),
    )

    preview = _json(stack, "batch", "preview", str(path), "--json")
    assert len(preview["messages"]) == 2

    batch = _json(stack, "batch", "submit", str(path), "--json")
    assert batch["counts"]["awaiting_approval"] == 2

    detail = _json(stack, "batch", "show", batch["id"], "--json")
    assert len(detail["recipients"]) == 2

    jobs = _json(stack, "job", "list", "--batch", batch["id"], "--json")
    assert len(jobs) == 2

    cancelled = _json(stack, "batch", "cancel", batch["id"], "--json", "--yes")
    assert cancelled["state"] == "cancelled"


def test_cli_output_is_plain_without_a_tty(stack_factory) -> None:
    stack = stack_factory()
    result = _cli(stack, "account", "list")
    assert result.returncode == 0, result.stderr
    assert "\033[" not in result.stdout
