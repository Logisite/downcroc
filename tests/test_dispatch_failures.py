from __future__ import annotations

import json
import os
import signal
import sqlite3

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def test_transient_retries_and_permanent_records_once(stack_factory) -> None:
    config = dispatch_config(
        max_attempts=3,
        retry_base_s=1,
        retry_cap_s=4,
    )
    stack = stack_factory(config_extra=config)
    batch = submit(
        stack,
        campaign_of(
            3,
            options={"approval": "auto"},
        )
        | {
            "messages": [
                {
                    "to": {"email": "transient-once@example.com"},
                    "subject": "Transient",
                    "text": "Body",
                },
                {
                    "to": {"email": "permanent-once@example.com"},
                    "subject": "Permanent",
                    "text": "Body",
                },
                {
                    "to": {"email": "good@example.com"},
                    "subject": "Good",
                    "text": "Body",
                },
            ]
        },
    )
    _done(stack, batch["id"])
    detail = stack.api.get(f"/api/batches/{batch['id']}")
    assert detail["counts"] == {"sent": 2, "failed": 1}

    failures = stack.api.get("/api/failed")
    assert len(failures) == 1
    failure = failures[0]
    assert failure["recipient"] == "permanent-once@example.com"
    assert failure["code"] == "smtp_550"

    log_file = stack.daemon.data_home / "downcroc" / "failed.jsonl"
    lines = [
        json.loads(line) for line in log_file.read_text().splitlines() if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["job"] == failure["job_id"]

    logged = events(stack)
    assert len(logged["job.failed"]) == 1
    assert logged["job.failed"][0]["job"] == failure["job_id"]
    retry_events = logged["job.retry"]
    assert retry_events[0]["attempt"] == 1
    assert retry_events[0]["in_s"] >= 1

    retried = stack.api.post(f"/api/failed/{failure['job_id']}/retry")
    assert retried["state"] == "queued"
    assert retried["attempts"] == 0
    until(lambda: stack.api.get("/api/failed") == [], timeout=30)
    _done(stack, batch["id"], timeout=30)

    detail = stack.api.get(f"/api/batches/{batch['id']}")
    assert detail["counts"] == {"sent": 3}
    recipients = {message["To"] for message in stack.fakes.sent()}
    assert any("permanent-once@example.com" in item for item in recipients)
    retried_sends = sum(
        1
        for message in stack.fakes.sent()
        if "permanent-once@example.com" in str(message["To"])
    )
    assert retried_sends == 1
    status, body = stack.api.raw("GET", f"/api/failed/{failure['job_id']}")
    assert status == 404
    assert body["error"] == "failure_not_found"

    stack.daemon.stop()
    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()
    assert stack.api.get("/api/failed") == []
    lines = [
        json.loads(line) for line in log_file.read_text().splitlines() if line.strip()
    ]
    assert lines == []


def test_retry_all_requeues_each_failure_once(stack_factory) -> None:
    stack = stack_factory(config_extra=dispatch_config())
    document = campaign_of(2, options={"approval": "auto"})
    document["messages"] = [
        {
            "to": {"email": "permanent-once-a@example.com"},
            "subject": "A",
            "text": "Body",
        },
        {
            "to": {"email": "permanent-once-b@example.com"},
            "subject": "B",
            "text": "Body",
        },
    ]
    batch = submit(stack, document)
    _done(stack, batch["id"])
    assert len(stack.api.get("/api/failed")) == 2

    retried = stack.api.post("/api/failed/retry", {})
    assert retried == {"retried": 2}
    until(lambda: stack.api.get("/api/failed") == [], timeout=30)
    _done(stack, batch["id"], timeout=30)

    assert stack.api.get(f"/api/batches/{batch['id']}")["counts"] == {"sent": 2}
    assert len(stack.fakes.sent()) == 2


def test_transient_retries_grow_until_exhausted(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(
            max_attempts=3,
            retry_base_s=1,
            retry_factor=2.0,
            retry_cap_s=10,
        )
    )
    document = campaign_of(1, options={"approval": "auto"})
    document["messages"] = [
        {
            "to": {"email": "transient@example.com"},
            "subject": "Always transient",
            "text": "Body",
        }
    ]
    submit(stack, document)

    until(lambda: stack.api.get("/api/failed") != [], timeout=30)
    failure = stack.api.get("/api/failed")[0]
    assert failure["attempts"] == 3
    retries = events(stack)["job.retry"]
    assert [item["attempt"] for item in retries] == [1, 2]
    assert [item["in_s"] for item in retries] == [1, 2]
    assert stack.fakes.sent() == []


def test_failure_file_reconciles_the_table_after_restart(stack_factory) -> None:
    config = dispatch_config()
    stack = stack_factory(config_extra=config)
    document = campaign_of(1, options={"approval": "auto"})
    document["messages"] = [
        {
            "to": {"email": "permanent@example.com"},
            "subject": "Permanent",
            "text": "Body",
        }
    ]
    batch = submit(stack, document)
    _done(stack, batch["id"])
    failure = stack.api.get("/api/failed")[0]

    os.kill(stack.daemon.process.pid, signal.SIGKILL)
    stack.daemon.process.wait(timeout=10)
    database = stack.daemon.data_home / "downcroc" / "downcroc.db"
    with sqlite3.connect(database) as connection:
        connection.execute("delete from failed_queue")
    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()

    until(lambda: stack.api.get("/api/failed") != [], timeout=30)
    reconciled = stack.api.get("/api/failed")
    assert [item["job_id"] for item in reconciled] == [failure["job_id"]]
    log_file = stack.daemon.data_home / "downcroc" / "failed.jsonl"
    assert len([line for line in log_file.read_text().splitlines() if line]) == 1
