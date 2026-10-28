from __future__ import annotations

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.seed import until

HOLD = {"not_before": "2999-01-01T00:00:00Z"}


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def _failures(stack: Stack, count: int) -> dict:
    document = campaign_of(0, options={"approval": "auto"})
    document["messages"] = [
        {
            "to": {"email": f"permanent-once-{index}@example.com"},
            "subject": f"Failure {index}",
            "text": "Body",
        }
        for index in range(1, count + 1)
    ]
    batch = submit(stack, document)
    _done(stack, batch["id"])
    return batch


def test_cancel_and_delete_one_job(stack: Stack) -> None:
    batch = submit(stack, campaign_of(2, options=HOLD))
    job = batch["recipients"][0]

    cancelled = stack.api.post(f"/api/jobs/{job['id']}/cancel")
    assert cancelled["state"] == "cancelled"

    status, body = stack.api.raw("DELETE", f"/api/jobs/{job['id']}")
    assert status == 409
    assert body["error"] == "confirmation_required"

    status, deleted = stack.api.raw("DELETE", f"/api/jobs/{job['id']}?confirm=true")
    assert status == 200
    assert deleted["state"] == "cancelled"

    status, body = stack.api.raw("GET", f"/api/jobs/{job['id']}")
    assert status == 404
    assert body["error"] == "job_not_found"

    counts = stack.api.get(f"/api/batches/{batch['id']}")["counts"]
    assert counts["awaiting_approval"] == 1
    assert counts.get("cancelled", 0) == 0


def test_delete_needs_force_for_unfinished_jobs(stack: Stack) -> None:
    batch = submit(stack, campaign_of(1, options=HOLD))
    job = batch["recipients"][0]

    status, body = stack.api.raw("DELETE", f"/api/jobs/{job['id']}?confirm=true")
    assert status == 409
    assert body["error"] == "job_not_terminal"

    status, body = stack.api.raw(
        "DELETE", f"/api/jobs/{job['id']}?confirm=true&dry_run=true"
    )
    assert status == 200
    assert body["dry_run"] is True
    assert stack.api.get(f"/api/jobs/{job['id']}")["state"] == "awaiting_approval"

    status, body = stack.api.raw(
        "DELETE", f"/api/jobs/{job['id']}?confirm=true&force=true"
    )
    assert status == 200
    status, _ = stack.api.raw("GET", f"/api/jobs/{job['id']}")
    assert status == 404


def test_reassign_moves_queued_jobs_and_repins_the_batch(stack: Stack) -> None:
    alice, bob = stack.accounts
    batch = submit(
        stack,
        campaign_of(
            2,
            options=HOLD,
            routing={"mode": "fixed", "account": alice},
        ),
    )
    payload = {"from_account_id": alice, "to_account_id": bob}

    status, body = stack.api.raw("POST", "/api/jobs/reassign", payload)
    assert status == 409
    assert body["error"] == "confirmation_required"

    preview = stack.api.post("/api/jobs/reassign", payload | {"dry_run": True})
    assert preview["jobs"] == 2
    assert preview["batches"] == 1
    jobs = stack.api.get(f"/api/jobs?batch={batch['id']}")
    assert {job["account_id"] for job in jobs} == {alice}

    moved = stack.api.post("/api/jobs/reassign", payload | {"confirm": True})
    assert moved["jobs"] == 2
    assert moved["batches"] == 1
    assert moved["skipped"] == []

    jobs = stack.api.get(f"/api/jobs?batch={batch['id']}")
    assert {job["account_id"] for job in jobs} == {bob}
    assert stack.api.get(f"/api/batches/{batch['id']}")["account_id"] == bob


def test_reassign_reports_sent_jobs_as_skipped(stack: Stack) -> None:
    alice, bob = stack.accounts
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": alice},
        ),
    )
    _done(stack, batch["id"])

    moved = stack.api.post(
        "/api/jobs/reassign",
        {
            "from_account_id": alice,
            "to_account_id": bob,
            "states": ["sent"],
            "confirm": True,
        },
    )
    assert moved["jobs"] == 0
    assert moved["skipped"][0]["reason"] == "state sent"


def test_account_deletion_preview_and_reassign(stack: Stack) -> None:
    alice, bob = stack.accounts
    submit(
        stack,
        campaign_of(
            2,
            options=HOLD,
            routing={"mode": "fixed", "account": alice},
        ),
    )

    preview = stack.api.get(f"/api/accounts/{alice}/deletion")
    assert preview["counts"]["jobs"] == 2
    assert preview["counts"]["awaiting_approval"] == 2
    assert "account_in_use" in preview["blockers"]

    status, body = stack.api.raw("DELETE", f"/api/accounts/{alice}")
    assert status == 409
    assert body["error"] == "confirmation_required"

    status, deleted = stack.api.raw(
        "DELETE",
        f"/api/accounts/{alice}?confirm=true&reassign_to={bob}",
    )
    assert status == 200
    assert deleted["reassigned"] == 2
    assert deleted["deleted_jobs"] == 0

    status, _ = stack.api.raw("GET", f"/api/accounts/{alice}")
    assert status == 404
    jobs = stack.api.get("/api/jobs")
    assert {job["account_id"] for job in jobs} == {bob}


def test_account_deletion_guards_history(stack: Stack) -> None:
    alice, _ = stack.accounts
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": alice},
        ),
    )
    _done(stack, batch["id"])

    status, body = stack.api.raw("DELETE", f"/api/accounts/{alice}?confirm=true")
    assert status == 409
    assert body["error"] == "account_in_use"

    status, body = stack.api.raw(
        "DELETE", f"/api/accounts/{alice}?confirm=true&force_jobs=true"
    )
    assert status == 409
    assert body["error"] == "account_in_use"

    status, deleted = stack.api.raw(
        "DELETE",
        f"/api/accounts/{alice}?confirm=true&force_jobs=true&force_history=true",
    )
    assert status == 200
    assert deleted["deleted_jobs"] == 1
    status, _ = stack.api.raw("GET", f"/api/accounts/{alice}")
    assert status == 404


def test_archive_hides_an_account_from_list_and_routing(stack: Stack) -> None:
    alice, bob = stack.accounts

    status, body = stack.api.raw("POST", f"/api/accounts/{bob}/archive")
    assert status == 409
    assert body["error"] == "confirmation_required"

    archived = stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")
    assert archived["archived_at"] is not None
    assert archived["watcher_enabled"] is False

    listed = {account["id"] for account in stack.api.get("/api/accounts")}
    assert listed == {alice}
    assert stack.api.get(f"/api/accounts/{bob}")["archived_at"] is not None

    batch = submit(stack, campaign_of(2, options=HOLD))
    counts = batch["routing"]["counts"]
    assert bob not in counts
    assert sum(counts.values()) == 2

    restored = stack.api.post(f"/api/accounts/{bob}/unarchive?confirm=true")
    assert restored["archived_at"] is None
    listed = {account["id"] for account in stack.api.get("/api/accounts")}
    assert listed == {alice, bob}


def test_batch_delete_requires_a_terminal_batch(stack: Stack) -> None:
    batch = submit(stack, campaign_of(2, options=HOLD))

    status, body = stack.api.raw("DELETE", f"/api/batches/{batch['id']}")
    assert status == 409
    assert body["error"] == "confirmation_required"

    status, body = stack.api.raw("DELETE", f"/api/batches/{batch['id']}?confirm=true")
    assert status == 409
    assert body["error"] == "batch_state_conflict"

    stack.api.post(f"/api/batches/{batch['id']}/cancel")

    status, preview = stack.api.raw(
        "DELETE", f"/api/batches/{batch['id']}?confirm=true&dry_run=true"
    )
    assert status == 200
    assert preview["jobs"] == 2

    status, deleted = stack.api.raw(
        "DELETE", f"/api/batches/{batch['id']}?confirm=true"
    )
    assert status == 200
    assert deleted["jobs"] == 2
    status, _ = stack.api.raw("GET", f"/api/batches/{batch['id']}")
    assert status == 404
    assert stack.api.get(f"/api/jobs?batch={batch['id']}") == []


def test_failure_forget_and_purge(stack_factory) -> None:
    stack = stack_factory(config_extra=dispatch_config())
    _failures(stack, 2)

    failures = stack.api.get("/api/failed")
    assert len(failures) == 2
    first = failures[0]

    status, body = stack.api.raw("DELETE", f"/api/failures/{first['job_id']}")
    assert status == 409
    assert body["error"] == "confirmation_required"

    status, forgotten = stack.api.raw(
        "DELETE", f"/api/failures/{first['job_id']}?confirm=true"
    )
    assert status == 200
    assert forgotten["forgotten"] is True
    assert len(stack.api.get("/api/failed")) == 1

    status, body = stack.api.raw("POST", "/api/failures/purge", {"states": ["failed"]})
    assert status == 409
    assert body["error"] == "confirmation_required"

    preview = stack.api.post(
        "/api/failures/purge", {"states": ["failed"], "dry_run": True}
    )
    assert preview == {"failures": 1, "dry_run": True}
    assert len(stack.api.get("/api/failed")) == 1

    purged = stack.api.post(
        "/api/failures/purge", {"states": ["failed"], "confirm": True}
    )
    assert purged == {"failures": 1, "dry_run": False}
    assert stack.api.get("/api/failed") == []
