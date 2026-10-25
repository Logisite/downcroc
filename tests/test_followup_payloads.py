from __future__ import annotations

from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.followups import (
    body,
    done,
    ids,
    job,
    recipient_job,
    reply,
    sent,
)
from tests.harness.seed import message, write_csv, write_json, write_template


def test_payload_csv_with_template_against_json_campaign(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = submit(
        stack,
        campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        ),
        "parent.json",
    )
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    write_template(
        stack.daemon.config,
        "bump",
        subject="CSV bump {{ name }}",
        body="Hello {{ name }}",
    )
    path = write_csv(
        input_files(stack),
        "bump.csv",
        "email,name\nperson1@example.com,Person 1\n",
    )

    status, created = stack.api.raw(
        "POST",
        f"/api/batches/{batch['id']}/followups",
        {"path": str(path), "template": "bump", "step": "csv-bump"},
    )
    assert status == 201
    assert created["kind"] == "follow_up"
    assert created["source_kind"] == "csv"
    assert created["template_ref"] == "bump"
    done(stack, created["id"])
    item = job(created, "person1@example.com")
    assert item["source_kind"] == "csv"
    assert item["source_key"] is None
    assert item["parent_job_id"] == initial["id"]
    outgoing = sent(stack, item["message_id"])
    assert outgoing["Subject"] == "CSV bump Person 1"
    assert body(outgoing) == "Hello Person 1"
    assert ids(outgoing, "In-Reply-To") == [initial["message_id"]]
    assert ids(outgoing, "References") == [initial["message_id"]]


def test_payload_gaps_extras_and_suppression(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = submit(
        stack,
        campaign_of(
            2,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        ),
        "payload-parent.json",
    )
    done(stack, batch["id"])
    first = recipient_job(batch, "person1@example.com")
    root = input_files(stack)

    only_first = write_json(
        root,
        "only-first.json",
        [message("person1@example.com", key="p1", subject="Again", text="Again")],
    )
    status, response = stack.api.raw(
        "POST",
        f"/api/batches/{batch['id']}/followups",
        {"path": str(only_first), "step": "again-1"},
    )
    assert status == 422
    assert "person2@example.com" in str(response)

    with_extra = write_json(
        root,
        "with-extra.json",
        [
            message("person1@example.com", key="p1", subject="Again", text="Again"),
            message("person2@example.com", key="p2", subject="Again", text="Again"),
            message("extra@example.com", key="p3", subject="Extra", text="Extra"),
        ],
    )
    created = stack.api.post(
        f"/api/batches/{batch['id']}/followups",
        {"path": str(with_extra), "step": "again-1"},
    )
    assert {item["recipient"] for item in created["recipients"]} == {
        "person1@example.com",
        "person2@example.com",
    }
    assert any("extra@example.com" in item for item in created["warnings"])
    done(stack, created["id"])

    reply(
        stack,
        account,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        in_reply_to=first["message_id"],
        references=(first["message_id"],),
        expected=1,
    )
    suppressed = stack.api.post(
        f"/api/batches/{batch['id']}/followups",
        {"path": str(with_extra), "step": "again-2"},
    )
    assert [item["recipient"] for item in suppressed["recipients"]] == [
        "person2@example.com"
    ]
    assert any("person1@example.com" in item for item in suppressed["warnings"])


def test_ready_payload_against_csv_campaign(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    write_template(
        stack.daemon.config,
        "initial",
        subject="Hi {{ name }}",
        body="Initial body",
    )
    path = write_csv(
        input_files(stack),
        "initial.csv",
        "email,name\nperson1@example.com,Person 1\n",
    )
    batch = stack.api.submit(str(path), template="initial")
    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "all"})
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    assert initial["source_kind"] == "csv"

    payload = write_json(
        input_files(stack),
        "ready.json",
        [
            message(
                "person1@example.com",
                key="p1",
                subject="JSON bump",
                text="JSON body",
            )
        ],
    )
    created = stack.api.post(
        f"/api/batches/{batch['id']}/followups",
        {"path": str(payload), "step": "json-bump"},
    )
    done(stack, created["id"])
    item = job(created, "person1@example.com")
    assert item["source_kind"] == "json"
    assert item["source_key"] == "p1"
    outgoing = sent(stack, item["message_id"])
    assert outgoing["Subject"] == "JSON bump"
    assert body(outgoing) == "JSON body"
    assert ids(outgoing, "In-Reply-To") == [initial["message_id"]]
