from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import input_files, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.seed import campaign, message, until, write_json

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
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _stats(stack: Stack) -> dict[str, dict]:
    rows = stack.api.get("/api/stats/accounts")["rows"]
    return {row["account_id"]: row for row in rows}


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def _one(recipient: str) -> dict:
    return campaign(
        [message(recipient, key="m1", subject="Hello")],
        options={"approval": "auto"},
    )


def test_cli_service_pause_is_reported_and_idempotent(stack_factory) -> None:
    stack = stack_factory(config_extra=dispatch_config())

    first = _json(
        stack,
        "service",
        "pause",
        "--reason",
        "smtp throttle",
        "--json",
    )
    assert first["changed"] is True
    assert first["sending"]["state"] == "paused"
    assert first["sending"]["reason"] == "smtp throttle"

    again = _json(stack, "service", "pause", "--json")
    assert again["changed"] is False

    assert stack.api.get("/api/health")["sending"] == "paused"
    status = _json(stack, "status", "--json")
    assert status["sending"]["state"] == "paused"
    assert status["sending"]["reason"] == "smtp throttle"

    resumed = _json(stack, "service", "resume", "--json")
    assert resumed["changed"] is True
    assert stack.api.get("/api/health")["sending"] == "running"
    assert _json(stack, "service", "resume", "--json")["changed"] is False


def test_service_hold_survives_a_restart(stack_factory) -> None:
    config = dispatch_config()
    stack = stack_factory(config_extra=config)
    _json(stack, "service", "pause", "--reason", "restart", "--json")

    stack.daemon.kill()
    stack.daemon.start(stack.fakes, config)
    assert stack.api.get("/api/health")["sending"] == "paused"

    _json(stack, "service", "resume", "--json")
    assert stack.api.get("/api/health")["sending"] == "running"


def test_cli_account_pause_stops_auto_work_until_resumed(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(tick_s=0.5, jitter_max=0),
        accounts=["alice@local.test"],
    )
    account_id = stack.accounts[0]

    held = _json(
        stack,
        "account",
        "pause",
        account_id,
        "--reason",
        "maintenance",
        "--json",
    )
    assert held[0]["account"]["paused_at"]
    assert held[0]["account"]["paused_reason"] == "maintenance"

    path = write_json(input_files(stack), "paused.json", _one("person@example.com"))
    batch = stack.api.post(
        "/api/batches",
        {"path": str(path), "account": account_id},
    )
    time.sleep(1.5)
    assert stack.fakes.sent() == []

    detail = stack.api.get(f"/api/batches/{batch['id']}")
    assert detail["eta"]["state"] == "paused"
    assert detail["eta"]["finish_at"] == {"earliest": None, "latest": None}

    resumed = _json(stack, "account", "resume", account_id, "--json")
    assert resumed[0]["account"]["paused_at"] is None
    _done(stack, batch["id"])
    assert len(stack.fakes.sent()) == 1


def test_batch_and_job_holds_release_queued_work(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(tick_s=0.5, jitter_max=0),
        accounts=["alice@local.test"],
    )
    batch = submit(
        stack,
        campaign(
            [message("person@example.com", key="m1", subject="Hello")],
            options={"approval": "review"},
        ),
    )
    stack.api.post(f"/api/batches/{batch['id']}/pause", {"reason": "hold"})
    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "all"})
    time.sleep(1.2)
    assert stack.fakes.sent() == []
    stack.api.post(f"/api/batches/{batch['id']}/resume", {"reason": "release"})
    _done(stack, batch["id"])

    held = submit(
        stack,
        campaign(
            [message("second@example.com", key="m1", subject="Hello")],
            options={"approval": "review"},
        ),
        name="job-hold.json",
    )
    job_id = stack.api.get(f"/api/batches/{held['id']}")["recipients"][0]["id"]
    paused = stack.api.post(f"/api/jobs/{job_id}/pause", {"reason": "hold"})
    assert paused["paused_at"]
    stack.api.post(f"/api/batches/{held['id']}/approve", {"mode": "all"})
    time.sleep(1.2)
    assert len(stack.fakes.sent()) == 1
    stack.api.post(f"/api/jobs/{job_id}/resume", {})
    _done(stack, held["id"])
    assert len(stack.fakes.sent()) == 2


def test_quota_counts_accepted_messages_only(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(
            tick_s=0.05,
            jitter_max=0,
            max_attempts=1,
            daily_allowance=10,
        ),
        accounts=["alice@local.test"],
    )
    account_id = stack.accounts[0]

    failed = submit(
        stack,
        _one("permanent@example.com"),
        name="failed.json",
    )
    _done(stack, failed["id"])
    row = _stats(stack)[account_id]
    assert row["used"] == 0
    assert row["reserved"] == 0
    assert row["available"] == 10

    accepted = submit(stack, _one("person@example.com"), name="accepted.json")
    _done(stack, accepted["id"])
    row = _stats(stack)[account_id]
    assert row["used"] == 1
    assert row["reserved"] == 0
    assert row["available"] == 9
