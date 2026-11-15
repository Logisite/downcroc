from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.seed import until

ROOT = Path(__file__).resolve().parents[2]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**stack.daemon.environment(), "COLUMNS": "200", "LINES": "60"}
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _sent_job(stack: Stack, count: int = 1, timeout: float = 30.0) -> dict:
    until(lambda: len(stack.fakes.sent()) >= count, timeout=timeout)
    found = stack.api.get("/api/jobs?state=sent")
    assert found, "no sent job appeared"
    return found[0]


def _unpinned_sent_job(stack: Stack, account_id: str) -> dict:
    stack.api.post("/api/service/pause", {"reason": "hold while unpinning"})
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account_id},
        ),
    )
    job = stack.api.get(f"/api/jobs?batch={batch['id']}")[0]
    assert job["sender_policy"] == "pinned"
    moved = stack.api.post(
        "/api/jobs/reassign",
        {"unpin": True, "job_ids": [job["id"]], "confirm": True},
    )
    assert moved["jobs"] == 1, moved
    stack.api.post("/api/service/resume", {})
    sent = _sent_job(stack)
    assert sent["id"] == job["id"]
    assert sent["sender_policy"] == "auto"
    assert sent["account_id"] is None
    return sent


def test_unpinned_auto_job_shows_the_real_sender(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    job = _unpinned_sent_job(stack, alice)

    plain = _cli(stack, "job", "show", job["id"])
    assert plain.returncode == 0, plain.stderr
    assert f"auto (sent from {alice})" in plain.stdout
    assert "alice@local.test" not in plain.stdout

    labelled = _cli(stack, "job", "show", job["id"], "--addresses")
    assert labelled.returncode == 0, labelled.stderr
    assert "auto (sent from alice@local.test)" in labelled.stdout
    assert alice not in labelled.stdout


def test_pinned_job_shows_the_address_on_request(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["bob@local.test"],
    )
    bob = stack.accounts[0]
    status, job = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": bob,
            "recipient": "person@example.com",
            "subject": "Pinned hello",
            "text": "Body",
        },
    )
    assert status == 201, job
    sent = stack.api.post(f"/api/jobs/{job['id']}/send")
    assert sent["state"] == "sent"

    plain = _cli(stack, "job", "show", job["id"])
    assert plain.returncode == 0, plain.stderr
    assert f"pinned {bob}" in plain.stdout

    labelled = _cli(stack, "job", "show", job["id"], "--addresses")
    assert labelled.returncode == 0, labelled.stderr
    assert "pinned bob@local.test" in labelled.stdout
    assert bob not in labelled.stdout


def test_attempts_show_addresses_and_json_stays_raw(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    job = _unpinned_sent_job(stack, alice)

    labelled = _cli(stack, "job", "attempts", job["id"], "--addresses")
    assert labelled.returncode == 0, labelled.stderr
    assert "alice@local.test" in labelled.stdout
    assert alice not in labelled.stdout

    machine = _cli(stack, "job", "attempts", job["id"], "--json")
    assert machine.returncode == 0, machine.stderr
    rows = json.loads(machine.stdout)
    assert rows
    assert rows[0]["account_id"] == alice
    assert rows[0]["outcome"] == "sent"
    assert rows[0]["accepted"] is True

    machine = _cli(stack, "job", "show", job["id"], "--json")
    assert machine.returncode == 0, machine.stderr
    shown = json.loads(machine.stdout)
    assert shown["account_id"] is None
    assert shown["sender_policy"] == "auto"
