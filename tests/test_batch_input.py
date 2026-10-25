from __future__ import annotations

import json

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, input_files
from tests.harness.campaigns import submit as submit_campaign
from tests.harness.logs import events
from tests.harness.seed import campaign, message, write_csv, write_json, write_template


def test_unsupported_schema_is_refused(stack: Stack) -> None:
    document = campaign_of(1)
    document["schema"] = "downcroc.campaign/v9"
    path = write_json(input_files(stack), "bad-schema.json", document)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})

    assert status == 422
    assert body["error"] == "unsupported_schema"
    assert stack.api.get("/api/batches") == []


def test_duplicate_address_names_both_keys(stack: Stack) -> None:
    document = campaign(
        [
            message("same@example.com", key="first"),
            message("same@example.com", key="second"),
        ]
    )
    path = write_json(input_files(stack), "duplicate.json", document)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})

    assert status == 422
    detail = body["details"][0]
    assert detail["code"] == "duplicate_address"
    assert "first" in detail["message"] and "second" in detail["message"]


def test_allow_duplicates_keeps_both_messages(stack: Stack) -> None:
    document = campaign(
        [
            message("same@example.com", key="first"),
            message("same@example.com", key="second"),
        ],
        options={"allow_duplicates": True},
    )
    batch = submit_campaign(stack, document, "allowed-duplicates.json")

    assert [job["source_key"] for job in batch["recipients"]] == ["first", "second"]


def test_unknown_message_field_is_refused(stack: Stack) -> None:
    document = campaign([message("ana@example.com", favourite_colour="blue")])
    path = write_json(input_files(stack), "unknown-field.json", document)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})

    assert status == 422
    assert body["details"][0]["code"] == "unknown_field"


def test_attachment_must_exist_and_stay_inside_the_source_directory(
    stack: Stack,
) -> None:
    missing = campaign([message("ana@example.com", attachments=["missing.pdf"])])
    path = write_json(input_files(stack), "missing-attachment.json", missing)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})
    assert status == 422
    assert body["details"][0]["code"] == "attachment_missing"

    escape = campaign([message("ana@example.com", attachments=["../secret.pdf"])])
    path = write_json(input_files(stack), "escape-attachment.json", escape)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})
    assert status == 422
    assert body["details"][0]["code"] == "attachment_path"

    absolute = campaign(
        [message("ana@example.com", attachments=[str(stack.root / "secret.pdf")])]
    )
    path = write_json(input_files(stack), "absolute-attachment.json", absolute)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})
    assert status == 422
    assert body["details"][0]["code"] == "attachment_path"


def test_producer_headers_are_stripped_and_reported(stack: Stack) -> None:
    document = campaign(
        [
            message(
                "ana@example.com",
                From="spoofed@evil.example",
                **{
                    "Message-ID": "<forged@evil.example>",
                    "In-Reply-To": "<parent@evil.example>",
                    "References": "<parent@evil.example>",
                    "Date": "Thu, 01 Jan 1970 00:00:00 +0000",
                    "Bcc": "hidden@evil.example",
                },
            )
        ]
    )
    batch = submit_campaign(stack, document, "headers.json")
    assert any("From" in item for item in batch["ignored"])
    assert any("Message-ID" in item for item in batch["ignored"])

    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "one"})
    sent = stack.fakes.sent()[0]
    assert "evil.example" not in sent["From"]
    assert sent["Bcc"] is None
    ignored = [
        item for item in events(stack)["input.field_ignored"] if item["field"] == "From"
    ]
    assert ignored


def test_csv_template_renders_rows_and_collapses_duplicates(stack: Stack) -> None:
    write_template(
        stack.daemon.config,
        "intro",
        subject="Hello {{ name }}",
        body="Hi {{ name }}, about {{ company }}.",
    )
    path = write_csv(
        input_files(stack),
        "rows.csv",
        "email,name,company\n"
        "ana@example.com,Ana,Northwind\n"
        "bo@example.com,Bo,Contoso\n"
        "ana@example.com,Ana,Northwind\n",
    )
    batch = stack.api.submit(str(path), template="intro")

    assert batch["source_kind"] == "csv"
    assert batch["template_ref"] == "intro"
    assert len(batch["recipients"]) == 2
    assert any("duplicate" in warning for warning in batch["warnings"])
    subjects = {job["subject"] for job in batch["recipients"]}
    assert subjects == {"Hello Ana", "Hello Bo"}
    assert events(stack)["template.rendered"][0]["name"] == "intro"


def test_csv_missing_variable_names_row_and_column(stack: Stack) -> None:
    write_template(
        stack.daemon.config, "needs", subject="Hi", body="About {{ company }}."
    )
    path = write_csv(
        input_files(stack),
        "no-company.csv",
        "email,name\nana@example.com,Ana\n",
    )
    status, body = stack.api.raw(
        "POST", "/api/batches", {"path": str(path), "template": "needs"}
    )

    assert status == 422
    assert body["details"][0]["code"] == "missing_variable"
    assert body["details"][0]["field"] == "text"
    assert body["details"][0]["row"] == 2


def test_csv_bad_row_reports_the_row(stack: Stack) -> None:
    write_template(stack.daemon.config, "plain", subject="Hi {{ name }}", body="Body")
    path = write_csv(
        input_files(stack),
        "bad-row.csv",
        "email,name\nana@example.com,Ana\nnot-an-address,Bo\n",
    )
    status, body = stack.api.raw(
        "POST", "/api/batches", {"path": str(path), "template": "plain"}
    )

    assert status == 422
    assert body["details"][0]["code"] == "invalid_address"
    assert body["details"][0]["row"] == 3


def test_bare_array_of_messages_imports(stack: Stack) -> None:
    path = write_json(input_files(stack), "bare.json", campaign_of(2)["messages"])
    batch = stack.api.submit(str(path))

    assert batch["source_kind"] == "json"
    assert [job["source_key"] for job in batch["recipients"]] == ["m1", "m2"]
    assert batch["campaign_key"] == "bare"


def test_thousand_message_sources_import(stack: Stack) -> None:
    json_batch = submit_campaign(stack, campaign_of(1000), "thousand.json")
    assert json_batch["counts"] == {
        "awaiting_approval": 1000,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert len(json_batch["recipients"]) == 1000

    write_template(stack.daemon.config, "bulk", subject="Hi {{ name }}", body="Body")
    rows = ["email,name"] + [
        f"bulk{index}@example.com,Person {index}" for index in range(1000)
    ]
    path = write_csv(input_files(stack), "thousand.csv", "\n".join(rows) + "\n")
    csv_batch = stack.api.submit(str(path), template="bulk")
    assert csv_batch["counts"] == {
        "awaiting_approval": 1000,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }


def test_resubmission_keeps_the_same_routing_spread(stack: Stack) -> None:
    document = campaign_of(12, key="stable-key")
    first = submit_campaign(stack, document, "first.json")
    second = submit_campaign(stack, document, "second.json")

    first_plan = {job["source_key"]: job["account_id"] for job in first["recipients"]}
    second_plan = {job["source_key"]: job["account_id"] for job in second["recipients"]}
    assert first_plan == second_plan


def test_followups_validate_and_create_no_jobs(stack: Stack) -> None:
    document = campaign(
        [
            message(
                "ana@example.com",
                key="only",
                followups={"bump": {"subject": "Re: hello", "text": "Bump"}},
            )
        ],
        followups=[
            {
                "key": "bump",
                "after_days": 3,
                "when": "no_reply",
                "text": "Bump",
            }
        ],
    )
    batch = submit_campaign(stack, document, "followups.json")

    assert batch["counts"] == {
        "awaiting_approval": 1,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }
    assert len(batch["recipients"]) == 1
    snapshot = stack.daemon.data_home / "downcroc" / "content" / batch["source_ref"]
    stored = json.loads(snapshot.read_text())
    assert stored["followups"][0]["key"] == "bump"
    assert stored["messages"][0]["followups"]["bump"]["text"] == "Bump"

    bad = campaign(
        [message("bo@example.com", key="bo", followups={"ghost": {"text": "Hi"}})]
    )
    path = write_json(input_files(stack), "bad-followup.json", bad)
    status, body = stack.api.raw("POST", "/api/batches", {"path": str(path)})
    assert status == 422
    assert body["details"][0]["code"] == "unknown_step"
    assert body["details"][0]["key"] == "bo"
