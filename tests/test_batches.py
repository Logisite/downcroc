from __future__ import annotations

import json
from email.utils import parseaddr

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.logs import events
from tests.harness.seed import campaign, message, write_csv, write_json, write_template


def test_submit_routes_and_snapshots(stack: Stack) -> None:
    response = submit(stack, campaign_of(8))

    assert response["source_kind"] == "json"
    assert response["state"] == "awaiting_approval"
    assert response["counts"] == {
        "awaiting_approval": 8,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert len(response["recipients"]) == 8
    assert len(response["samples"]) == 5
    assert all(sample["text"] == "Body" for sample in response["samples"])
    assert {sample["email"] for sample in response["samples"]} <= {
        job["recipient"] for job in response["recipients"]
    }
    assert response["routing"]["mode"] == "auto"
    assert sum(response["routing"]["counts"].values()) == 8
    assert set(response["routing"]["counts"]) <= set(stack.accounts)
    assert len(response["source_hash"]) == 64

    message_ids = {job["message_id"] for job in response["recipients"]}
    assert len(message_ids) == 8

    snapshot = stack.daemon.data_home / "downcroc" / "content" / response["source_ref"]
    document = json.loads(snapshot.read_text())
    assert document["schema"] == "downcroc.campaign/v1"
    assert len(document["messages"]) == 8


def test_approve_one_sends_one_and_leaves_the_rest_locked(stack: Stack) -> None:
    batch = submit(stack, campaign_of(3))
    approved = stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "one"})

    assert approved["counts"] == {
        "sent": 1,
        "awaiting_approval": 2,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert approved["state"] == "awaiting_approval"
    sent = stack.fakes.sent()
    assert len(sent) == 1
    assert parseaddr(sent[0]["To"])[1].endswith("@example.com")
    assert sent[0]["Message-ID"].startswith("<")

    status, body = stack.api.raw(
        "POST", f"/api/batches/{batch['id']}/approve", {"mode": "one"}
    )
    assert status == 409
    assert body["error"] == "sample_already_sent"
    approved_events = events(stack)["batch.approved"]
    assert approved_events[0]["sample"] is True


def test_approve_all_queues_everything(stack: Stack) -> None:
    batch = submit(
        stack,
        campaign_of(3, options={"not_before": "2999-01-01T00:00:00Z"}),
    )
    approved = stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "all"})

    assert approved["counts"] == {
        "queued": 3,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert stack.fakes.sent() == []
    assert approved["approved_at"] is not None


def test_auto_approval_skips_the_review_gate(stack: Stack) -> None:
    batch = submit(
        stack,
        campaign_of(
            2,
            options={
                "approval": "auto",
                "not_before": "2999-01-01T00:00:00Z",
            },
        ),
    )

    assert batch["state"] == "sending"
    assert batch["counts"] == {
        "queued": 2,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }


def test_cancel_stops_queued_jobs(stack: Stack) -> None:
    batch = submit(
        stack,
        campaign_of(2, options={"not_before": "2999-01-01T00:00:00Z"}),
    )
    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "all"})
    cancelled = stack.api.post(f"/api/batches/{batch['id']}/cancel")

    assert cancelled["state"] == "cancelled"
    assert cancelled["counts"] == {
        "cancelled": 2,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert events(stack)["batch.cancelled"][0]["sent_so_far"] == 0


def test_cancel_reports_what_was_already_sent(stack: Stack) -> None:
    batch = submit(stack, campaign_of(3))
    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "one"})
    cancelled = stack.api.post(f"/api/batches/{batch['id']}/cancel")

    assert cancelled["counts"] == {
        "sent": 1,
        "cancelled": 2,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }


def test_fixed_routing_sends_every_message_from_one_account(stack: Stack) -> None:
    account = stack.accounts[1]
    batch = submit(
        stack,
        campaign_of(3, routing={"mode": "fixed", "account": account}),
    )

    assert batch["account_id"] == account
    assert {job["account_id"] for job in batch["recipients"]} == {account}


def test_preview_csv_row_by_row_number(stack: Stack) -> None:
    write_template(
        stack.daemon.config, "row-preview", subject="Hi {{ name }}", body="Body"
    )
    path = write_csv(
        input_files(stack),
        "preview.csv",
        "email,name\nana@example.com,Ana\nbo@example.com,Bo\n",
    )
    preview = stack.api.preview(str(path), template="row-preview", key="3")

    assert [item["email"] for item in preview["messages"]] == ["bo@example.com"]
    assert preview["messages"][0]["row"] == 3


def test_preview_renders_without_creating_a_batch(stack: Stack) -> None:
    path = write_json(input_files(stack), "preview.json", campaign_of(2))
    preview = stack.api.preview(str(path))

    assert len(preview["messages"]) == 2
    assert preview["messages"][0]["account_id"] in stack.accounts

    single = stack.api.preview(str(path), key="m2")
    assert [item["key"] for item in single["messages"]] == ["m2"]
    assert stack.api.get("/api/batches") == []


def test_validation_leaves_no_batch_and_is_logged(stack: Stack) -> None:
    document = campaign_of(1)
    document["messages"] = [
        message("same@example.com", key="a"),
        message("same@example.com", key="b"),
    ]
    path = write_json(input_files(stack), "invalid.json", document)
    status, _ = stack.api.raw("POST", "/api/batches", {"path": str(path)})
    assert status == 422
    assert stack.api.get("/api/batches") == []

    logged = events(stack)
    assert "validation.failed" in logged
    assert logged["validation.failed"][0]["count"] == 1
    assert logged["validation.row_rejected"][0]["code"] == "duplicate_address"


def test_submit_logs_the_intake_stages(stack: Stack) -> None:
    submit(stack, campaign_of(2), "logged.json")
    logged = events(stack)

    for name in (
        "input.detected",
        "input.parsed",
        "routing.resolved",
        "snapshot.stored",
        "batch.created",
    ):
        assert name in logged


def test_submit_key_creates_one_job_and_a_retry_reuses_it(stack: Stack) -> None:
    path = write_json(input_files(stack), "single.json", campaign_of(3))

    status, first = stack.api.raw(
        "POST", "/api/batches", {"path": str(path), "key": "m2"}
    )
    assert status == 201
    assert first["reused"] is False
    assert [job["source_key"] for job in first["recipients"]] == ["m2"]
    assert [sample["key"] for sample in first["samples"]] == ["m2"]

    status, second = stack.api.raw(
        "POST", "/api/batches", {"path": str(path), "key": "m2"}
    )
    assert status == 200
    assert second["reused"] is True
    assert second["id"] == first["id"]
    assert len(stack.api.get("/api/batches")) == 1
    assert events(stack)["batch.reused"][0]["batch"] == first["id"]


def test_submit_key_of_another_message_creates_another_batch(stack: Stack) -> None:
    path = write_json(input_files(stack), "keys.json", campaign_of(2))

    first = stack.api.submit(str(path), key="m1")
    second = stack.api.submit(str(path), key="m2")

    assert second["reused"] is False
    assert second["id"] != first["id"]
    assert [job["source_key"] for job in second["recipients"]] == ["m2"]
    assert len(stack.api.get("/api/batches")) == 2


def test_submit_key_of_edited_source_creates_a_new_batch(stack: Stack) -> None:
    path = write_json(input_files(stack), "edited.json", campaign_of(1))
    first = stack.api.submit(str(path), key="m1")

    write_json(
        input_files(stack),
        "edited.json",
        campaign([message("person1@example.com", key="m1", subject="Edited")]),
    )
    second = stack.api.submit(str(path), key="m1")

    assert second["reused"] is False
    assert second["id"] != first["id"]
    assert second["recipients"][0]["subject"] == "Edited"
    assert len(stack.api.get("/api/batches")) == 2


def test_submit_with_an_unknown_key_creates_nothing(stack: Stack) -> None:
    path = write_json(input_files(stack), "missing.json", campaign_of(2))
    status, body = stack.api.raw(
        "POST", "/api/batches", {"path": str(path), "key": "m9"}
    )

    assert status == 422
    assert body["error"] == "batch_invalid"
    assert "m9" in body["message"]
    assert stack.api.get("/api/batches") == []


def test_submit_without_a_key_is_never_reused(stack: Stack) -> None:
    path = write_json(input_files(stack), "whole.json", campaign_of(2))

    first = stack.api.submit(str(path))
    second = stack.api.submit(str(path))

    assert second["reused"] is False
    assert second["id"] != first["id"]
    assert len(stack.api.get("/api/batches")) == 2
