from __future__ import annotations

from tests.followups.support import (
    cli,
    cli_json,
    declare,
    declare_ok,
    parent,
    patch,
    payload,
    remove,
    retire,
    row,
    status_of,
)
from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.followups import (
    age_jobs,
    body,
    done,
    ids,
    job,
    recipient_job,
    reply,
    sent,
    step,
)
from tests.harness.logs import events
from tests.harness.replies import account_address
from tests.harness.seed import message, until, write_json


def test_shared_declaration_threads_and_applies_overrides(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = parent(stack, 2, "shared.json")
    first = recipient_job(batch, "person1@example.com")
    second = recipient_job(batch, "person2@example.com")
    report = declare_ok(
        stack,
        batch["id"],
        "fu1",
        patch(overrides={"m1": {"skip": True}, "m2": {"subject": "Custom subject"}}),
        "fu1.json",
    )
    assert row(report, "fu1")["version"] == 1
    age_jobs(stack, [first["id"], second["id"]], 2)

    child = step(stack, batch["id"], "fu1")
    done(stack, child["id"])
    assert [item["recipient"] for item in child["recipients"]] == [
        "person2@example.com"
    ]
    item = job(child, "person2@example.com")
    assert item["account_id"] == account
    assert item["thread_root_job_id"] == second["id"]
    outgoing = sent(stack, item["message_id"])
    assert outgoing["Subject"] == "Custom subject"
    assert ids(outgoing, "In-Reply-To") == [second["message_id"]]
    assert ids(outgoing, "References") == [second["message_id"]]
    assert account_address(stack, account) in (outgoing["From"] or "")

    logged = events(stack)
    assert logged["followup.declared"][-1]["overrides_count"] == 2
    linked = logged["thread.linked"][-1]
    assert (linked["parent"], linked["root"]) == (second["id"], second["id"])
    assert linked["in_reply_to"] == second["message_id"]
    assert logged["job.sent"][-1]["references_count"] == 1


def test_status_scheduled_pending_and_dry_run_writes_nothing(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "schedule.json")
    initial = recipient_job(batch, "person1@example.com")
    dry = declare_ok(stack, batch["id"], "fu1", patch(30), "dry.json", dry_run=True)
    assert dry["dry_run"] is True and row(dry, "fu1")["version"] == 1
    assert status_of(stack, batch["id"])["steps"] == []

    declared = declare_ok(stack, batch["id"], "fu1", patch(30), "later.json")
    assert row(declared, "fu1")["state"] == "scheduled"
    assert row(declared, "fu1")["counts"]["not_due"] == 1
    age_jobs(stack, [initial["id"]], 40)
    until(lambda: row(status_of(stack, batch["id"]), "fu1")["state"] == "pending")


def test_update_requires_version_and_replaces_overrides(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 2, "update.json")
    initial = [item["id"] for item in batch["recipients"]]
    declare_ok(
        stack,
        batch["id"],
        "fu1",
        patch(30, overrides={"m1": {"skip": True}}),
        "v1.json",
    )
    status, body = declare(stack, batch["id"], "fu1", patch(30), "v1b.json")
    assert (status, body["error"]) == (409, "followup_version_required")

    updated = declare_ok(stack, batch["id"], "fu1", patch(30), "v2.json", version=1)
    assert row(updated, "fu1")["version"] == 2
    conflict, body = declare(stack, batch["id"], "fu1", patch(30), "v3.json", version=1)
    assert (conflict, body["error"]) == (409, "followup_version_conflict")
    age_jobs(stack, initial, 40)
    child = step(stack, batch["id"], "fu1")
    assert {item["recipient"] for item in child["recipients"]} == {
        "person1@example.com",
        "person2@example.com",
    }


def test_remove_before_send_cancels_child_and_allows_redeclare(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "remove.json")
    initial = recipient_job(batch, "person1@example.com")
    declare_ok(
        stack, batch["id"], "fu1", patch(1, require_approval=True), "remove-fu1.json"
    )
    age_jobs(stack, [initial["id"]], 2)
    child = step(stack, batch["id"], "fu1")
    until(
        lambda: (
            stack.api.get(f"/api/batches/{child['id']}")["state"] == "awaiting_approval"
        )
    )
    status, removed = remove(stack, batch["id"], "fu1", 1)
    assert status == 200, removed
    assert row(removed, "fu1")["state"] == "retired"
    cancelled = stack.api.get(f"/api/batches/{child['id']}")
    assert cancelled["state"] == "cancelled"
    assert {item["state"] for item in cancelled["recipients"]} == {"cancelled"}
    assert len(stack.fakes.sent()) == 1
    again = declare_ok(stack, batch["id"], "fu1b", patch(30), "remove-again.json")
    assert row(again, "fu1b")["state"] == "scheduled"


def test_retire_after_send_keeps_child_and_blocks_the_key(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "retire.json")
    initial = recipient_job(batch, "person1@example.com")
    declare_ok(stack, batch["id"], "fu1", patch(1), "retire-fu1.json")
    age_jobs(stack, [initial["id"]], 2)
    child = step(stack, batch["id"], "fu1")
    done(stack, child["id"])

    status, retired = retire(stack, batch["id"], "fu1", 1)
    assert status == 200, retired
    assert row(retired, "fu1")["state"] == "retired"
    assert row(retired, "fu1")["child_batch_id"] == child["id"]
    used, body = declare(stack, batch["id"], "fu1", patch(30), "retire-again.json")
    assert (used, body["error"]) == (409, "followup_step_used")
    assert "fu1b" in (body.get("hint") or "")
    newer = declare_ok(stack, batch["id"], "fu1b", patch(30), "retire-new.json")
    assert row(newer, "fu1b")["state"] == "scheduled"
    assert events(stack)["followup.retired"][-1]["sent_jobs"] == 1


def test_invalid_declarations_leave_the_table_unchanged(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "invalid.json")
    declare_ok(stack, batch["id"], "fu1", patch(30), "good.json")
    status, body = declare(
        stack,
        batch["id"],
        "fu1",
        patch(30, overrides={"nope": {"skip": True}}),
        "unknown-override.json",
        version=1,
    )
    assert (status, body["error"]) == (422, "followup_override_unknown")
    status, body = declare(
        stack, batch["id"], "fu2", patch(30, extra_field=True), "unknown-field.json"
    )
    assert (status, body["error"]) == (422, "followup_invalid")
    kept = status_of(stack, batch["id"])
    assert all(item["step"] != "fu2" for item in kept["steps"])

    review = submit(stack, campaign_of(1), "unsent.json")
    assert review["state"] == "awaiting_approval"
    status, body = declare(stack, review["id"], "fu1", patch(1), "unsent-fu.json")
    assert (status, body["error"]) == (422, "followup_parent_invalid")


def test_payload_declaration_matches_recipients_and_ignores_headers(
    stack_factory,
) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 2, "payload.json")
    initial = [item["id"] for item in batch["recipients"]]
    schedule = {"after_days": 1, "when": "no_reply"}
    gap = payload(schedule, [message("person1@example.com", key="m1", text="One")])
    status, detail = declare(stack, batch["id"], "p1", gap, "gap.json")
    assert (status, detail["error"]) == (422, "followup_payload_gap")
    extra = payload(
        schedule,
        [
            message("person1@example.com", key="m1", text="One"),
            message("person2@example.com", key="m2", text="Two"),
            message("extra@example.com", key="m3", text="Extra"),
        ],
    )
    status, detail = declare(stack, batch["id"], "p1", extra, "extra.json")
    assert (status, detail["error"]) == (422, "followup_payload_extra")
    custom = payload(
        schedule,
        [
            message(
                "person1@example.com",
                key="m1",
                subject="A different note",
                text="Custom one",
                in_reply_to="<ignored@example.com>",
            ),
            message("person2@example.com", key="m2", subject="", text="Custom two"),
        ],
    )
    report = declare_ok(stack, batch["id"], "p1", custom, "custom.json")
    assert row(report, "p1")["kind"] == "payload"
    assert events(stack)["payload_header_ignored"]
    age_jobs(stack, initial, 2)
    child = step(stack, batch["id"], "p1")
    done(stack, child["id"])
    one = sent(stack, job(child, "person1@example.com")["message_id"])
    two = sent(stack, job(child, "person2@example.com")["message_id"])
    assert (one["Subject"], body(one)) == ("A different note", "Custom one")
    assert (two["Subject"], body(two)) == ("Re: Subject 2", "Custom two")
    assert ids(one, "In-Reply-To") == [
        recipient_job(batch, "person1@example.com")["message_id"]
    ]


def test_auto_parent_resolves_the_actual_sender(stack_factory) -> None:
    stack = stack_factory(
        accounts=["alice@local.test", "bob@local.test"],
        config_extra=dispatch_config(daily_allowance=10),
    )
    batch = submit(stack, campaign_of(1), "auto.json")
    initial = recipient_job(batch, "person1@example.com")
    stack.api.post(
        "/api/jobs/reassign",
        {"job_ids": [initial["id"]], "unpin": True, "confirm": True},
    )
    stack.api.post(f"/api/batches/{batch['id']}/approve", {"mode": "all"})
    done(stack, batch["id"])
    initial = recipient_job(
        stack.api.get(f"/api/batches/{batch['id']}"), "person1@example.com"
    )
    assert initial["account_id"] is None
    sender = stack.api.get(f"/api/jobs/{initial['id']}/attempts")[-1]["account_id"]
    assert sender is not None
    declare_ok(stack, batch["id"], "fu1", patch(1), "auto-fu.json")
    age_jobs(stack, [initial["id"]], 2)
    child = step(stack, batch["id"], "fu1")
    done(stack, child["id"])
    item = job(child, "person1@example.com")
    assert (item["account_id"], item["sender_policy"]) == (sender, "pinned")
    outgoing = sent(stack, item["message_id"])
    assert account_address(stack, sender) in (outgoing["From"] or "")
    assert events(stack)["job.sent"][-1]["thread_root"] == initial["id"]


def test_when_always_ignores_a_reply_and_missing_payload_is_isolated(
    stack_factory,
) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = parent(stack, 2, "always.json")
    initial = recipient_job(batch, "person1@example.com")
    reply(
        stack,
        account,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        in_reply_to=initial["message_id"],
        references=(initial["message_id"],),
        expected=1,
    )
    declare_ok(stack, batch["id"], "always", patch(30, when="always"), "always-fu.json")
    assert row(status_of(stack, batch["id"]), "always")["state"] == "scheduled"
    assert retire(stack, batch["id"], "always", 1)[0] == 200
    lost = payload(
        {"after_days": 1, "when": "no_reply"},
        [
            message("person1@example.com", key="m1", text="Payload"),
            message("person2@example.com", key="m2", text="Payload"),
        ],
    )
    declare_ok(stack, batch["id"], "lost", lost, "lost.json")
    declare_ok(stack, batch["id"], "kept", patch(1), "kept.json")
    content = (
        stack.daemon.data_home
        / "downcroc"
        / "content"
        / "batches"
        / batch["id"]
        / "followups"
        / "lost.json"
    )
    content.unlink()
    age_jobs(stack, [item["id"] for item in batch["recipients"]], 2)
    done(stack, step(stack, batch["id"], "kept")["id"])
    lost_row = row(status_of(stack, batch["id"]), "lost")
    assert (lost_row["state"], lost_row["detail"]) == ("broken", "payload_missing")
    assert any(
        item["step"] == "lost" and item["code"] == "followup_payload_missing"
        for item in events(stack)["followup.rejected"]
    )


def test_immediate_payload_rejects_account_and_duplicate_with_correlation(
    stack_factory,
) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "immediate.json")
    payload = write_json(
        input_files(stack),
        "immediate-fu.json",
        [{"to": {"email": "person1@example.com"}, "subject": "", "text": "Again"}],
    )
    status, body = stack.api.raw(
        "POST",
        f"/api/batches/{batch['id']}/followups",
        {"path": str(payload), "step": "now", "account": stack.accounts[0]},
    )
    assert status == 422 and "account" in body["fields"]
    created = stack.api.post(
        f"/api/batches/{batch['id']}/followups",
        {"path": str(payload), "step": "now"},
    )
    done(stack, created["id"])
    outgoing = sent(stack, job(created, "person1@example.com")["message_id"])
    assert outgoing["Subject"] == "Re: Subject 1"
    status, body = stack.api.raw(
        "POST",
        f"/api/batches/{batch['id']}/followups",
        {"path": str(payload), "step": "now"},
    )
    assert (status, body["error"]) == (409, "followup_step_used")
    rejected = events(stack)["followup.rejected"][-1]
    domain = events(stack)["api.domain_error"][-1]
    assert rejected["correlation_id"] == domain["correlation_id"]


def test_cli_followups_surface(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    batch = parent(stack, 1, "cli.json")
    path = write_json(input_files(stack), "cli-fu.json", patch(30))
    common = ("batch", "followups", "declare", batch["id"], str(path), "--step", "fu1")
    assert cli_json(stack, *common, "--dry-run", "--json")["dry_run"] is True
    report = cli_json(stack, *common, "--json")
    assert row(report, "fu1")["state"] == "scheduled"
    report = cli_json(stack, "batch", "followups", "status", batch["id"], "--json")
    assert row(report, "fu1")["version"] == 1
    report = cli_json(
        stack,
        "batch",
        "followups",
        "retire",
        batch["id"],
        "--step",
        "fu1",
        "--yes",
        "--json",
    )
    assert row(report, "fu1")["state"] == "retired"
    assert "shared" in cli(stack, "help", "followups").stdout
    examples = cli_json(stack, "batch", "example", "--kind", "followups", "--json")
    assert "shared.json" in examples and "payload.json" in examples
    unsupported = cli(
        stack,
        "batch",
        "followup",
        batch["id"],
        str(path),
        "--step",
        "x",
        "--account",
        stack.accounts[0],
    )
    assert unsupported.returncode == 2
