from __future__ import annotations

from pathlib import Path

from tests.harness.campaigns import campaign_of, submit
from tests.harness.logs import events


def test_request_failures_are_structured(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])

    status, body = stack.api.raw("GET", "/api/jobs/job_missing")
    assert status == 404
    assert body["error"] == "job_not_found"
    failed = events(stack)["api.request_failed"][-1]
    assert failed["method"] == "GET"
    assert failed["path"] == "/api/jobs/job_missing"
    assert failed["status"] == 404
    assert failed["code"] == "job_not_found"
    assert failed["request_id"]
    assert failed["duration_ms"] >= 0


def test_auth_rejections_are_logged_without_the_token(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    token = stack.api.token()

    status, _ = stack.api.raw("GET", "/api/accounts", auth=False)
    assert status == 401
    rejected = events(stack)["api.auth_rejected"][-1]
    assert rejected["reason"] == "unauthorized"
    assert rejected["client"]
    assert token not in str(rejected)


def test_boot_identity_and_recovery_are_logged(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    started = events(stack)["daemon.start"][-1]
    assert "commit" in started

    stack.daemon.kill()
    stack.daemon.start(stack.fakes, preserve_config=True)
    stack.api.unlock()

    recovered = events(stack)["daemon.recovered"][-1]
    assert recovered["previous_pid"] > 0
    assert recovered["previous_started_at"]
    assert recovered["clean"] is False


def test_routing_and_batch_events_name_their_source(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    batch = submit(stack, campaign_of(2, options={"approval": "review"}))
    found = events(stack)
    routing = found["routing.resolved"][-1]
    assert routing["counts"]
    assert sum(routing["counts"].values()) == 2
    created = found["batch.created"][-1]
    assert created["batch"] == batch["id"]
    assert Path(created["source"]).name
