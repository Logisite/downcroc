from __future__ import annotations

from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.followups import (
    age_jobs,
    batches,
    body,
    counts,
    done,
    ids,
    job,
    recipient_job,
    reply,
    sent,
    step,
    wait_state,
)
from tests.harness.logs import events
from tests.harness.replies import account_address, deliver_dsn, sync_and_wait
from tests.harness.seed import message, until


def test_declared_steps_follow_threads_and_skip_repliers(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    document = campaign_of(
        2,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {
                "key": "bump-1",
                "after_days": 1,
                "subject": "Bump one",
                "text": "Bump one body",
            },
            {
                "key": "bump-2",
                "after_days": 2,
                "subject": "Bump two",
                "text": "Bump two body",
            },
        ],
    )
    batch = submit(stack, document, "steps.json")
    done(stack, batch["id"])
    first = recipient_job(batch, "person1@example.com")
    second = recipient_job(batch, "person2@example.com")

    reply(
        stack,
        account,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        in_reply_to=first["message_id"],
        references=(first["message_id"],),
        expected=1,
    )
    age_jobs(stack, [first["id"], second["id"]], 3)

    step_one = step(stack, batch["id"], "bump-1")
    done(stack, step_one["id"])
    assert step_one["kind"] == "follow_up"
    assert step_one["parent_batch_id"] == batch["id"]
    assert step_one["options"]["step"] == "bump-1"
    assert [item["recipient"] for item in step_one["recipients"]] == [
        "person2@example.com"
    ]
    bump_one = job(step_one, "person2@example.com")
    assert bump_one["account_id"] == account
    assert bump_one["parent_job_id"] == second["id"]
    assert bump_one["thread_root_job_id"] == second["id"]
    assert bump_one["step_key"] == "bump-1"
    sent_one = sent(stack, bump_one["message_id"])
    assert sent_one["Subject"] == "Bump one"
    assert body(sent_one) == "Bump one body"
    assert ids(sent_one, "In-Reply-To") == [second["message_id"]]
    assert ids(sent_one, "References") == [second["message_id"]]
    assert counts(stack, batch["id"])["inbound"] == 1
    assert counts(stack, batch["id"])["replies"] == 1
    assert counts(stack, step_one["id"])["inbound"] == 0

    age_jobs(stack, [bump_one["id"]], 3)
    step_two = step(stack, batch["id"], "bump-2")
    done(stack, step_two["id"])
    bump_two = job(step_two, "person2@example.com")
    assert bump_two["parent_job_id"] == bump_one["id"]
    sent_two = sent(stack, bump_two["message_id"])
    assert sent_two["Subject"] == "Bump two"
    assert ids(sent_two, "In-Reply-To") == [bump_one["message_id"]]
    assert ids(sent_two, "References") == [
        second["message_id"],
        bump_one["message_id"],
    ]

    reply(
        stack,
        account,
        from_address="person2@example.com",
        subject="Re: Bump two",
        in_reply_to=bump_two["message_id"],
        references=(
            second["message_id"],
            bump_one["message_id"],
            bump_two["message_id"],
        ),
        expected=2,
    )
    until(lambda: counts(stack, step_two["id"])["inbound"] == 1)
    assert counts(stack, step_two["id"]) == {
        "sent": 1,
        "inbound": 1,
        "replies": 1,
        "late_replies": 0,
        "bounces": 0,
    }
    assert counts(stack, batch["id"])["inbound"] == 1

    logged = events(stack)
    created = logged["followup.created"]
    assert {item["step"] for item in created} == {"bump-1", "bump-2"}
    assert "followup.planned" in logged
    assert any(
        item["reason"] == "replied"
        and item["job"] == first["id"]
        and item["step"] == "bump-1"
        for item in logged["followup.skipped"]
    )


def test_failed_step_anchors_the_next_to_the_last_sent(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {"key": "bump-1", "after_days": 1, "subject": "One", "text": "One"},
            {"key": "bump-2", "after_days": 2, "subject": "Two", "text": "Two"},
        ],
    )
    document["messages"] = [
        message("secondfails@example.com", key="m1", subject="Start", text="Start")
    ]
    batch = submit(stack, document, "failure.json")
    done(stack, batch["id"])
    initial = recipient_job(batch, "secondfails@example.com")
    age_jobs(stack, [initial["id"]], 3)

    failed = step(stack, batch["id"], "bump-1")
    wait_state(stack, failed["id"], "secondfails@example.com", "failed")
    done(stack, failed["id"])

    next_step = step(stack, batch["id"], "bump-2")
    done(stack, next_step["id"])
    next_job = job(next_step, "secondfails@example.com")
    assert next_job["parent_job_id"] == initial["id"]
    assert next_job["step_key"] == "bump-2"
    outgoing = sent(stack, next_job["message_id"])
    assert ids(outgoing, "In-Reply-To") == [initial["message_id"]]
    assert ids(outgoing, "References") == [initial["message_id"]]


def test_overrides_replace_content_and_skip_opts_out(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    document = campaign_of(
        2,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {
                "key": "bump-1",
                "after_days": 1,
                "subject": "Shared",
                "text": "Shared body",
            }
        ],
    )
    document["messages"][0]["followups"] = {
        "bump-1": {"subject": "Custom", "text": "Custom body"}
    }
    document["messages"][1]["followups"] = {"bump-1": {"skip": True}}
    batch = submit(stack, document, "overrides.json")
    done(stack, batch["id"])
    age_jobs(stack, [item["id"] for item in batch["recipients"]], 2)

    step_one = step(stack, batch["id"], "bump-1")
    done(stack, step_one["id"])
    assert [item["recipient"] for item in step_one["recipients"]] == [
        "person1@example.com"
    ]
    first = job(step_one, "person1@example.com")
    outgoing = sent(stack, first["message_id"])
    assert outgoing["Subject"] == "Custom"
    assert body(outgoing) == "Custom body"
    assert any(
        item["step"] == "bump-1" and item["reason"] == "override"
        for item in events(stack)["followup.skipped"]
    )


def test_approval_restart_and_later_step_without_approval(stack_factory) -> None:
    config = dispatch_config()
    stack = stack_factory(accounts=["alice@local.test"], config_extra=config)
    account = stack.accounts[0]
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {
                "key": "bump-1",
                "after_days": 1,
                "subject": "One",
                "text": "One",
                "require_approval": True,
            },
            {"key": "bump-2", "after_days": 1, "subject": "Two", "text": "Two"},
        ],
    )
    batch = submit(stack, document, "approval.json")
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    age_jobs(stack, [initial["id"]], 2)

    step_one = step(stack, batch["id"], "bump-1")
    assert step_one["state"] == "awaiting_approval"
    assert len(stack.fakes.sent()) == 1
    assert [item["id"] for item in batches(stack, batch["id"])] == [step_one["id"]]

    before = len(events(stack)["followup.planned"])
    stack.daemon.stop()
    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()
    until(lambda: len(events(stack).get("followup.planned", [])) > before)
    assert len(batches(stack, batch["id"])) == 1
    assert len(step_one["recipients"]) == 1

    stack.api.post(f"/api/batches/{step_one['id']}/approve", {"mode": "all"})
    done(stack, step_one["id"])
    assert len(stack.fakes.sent()) == 2
    bump_one = job(
        stack.api.get(f"/api/batches/{step_one['id']}"), "person1@example.com"
    )
    age_jobs(stack, [bump_one["id"]], 2)

    step_two = step(stack, batch["id"], "bump-2")
    assert step_two["state"] in {"sending", "done"}
    assert step_two["approval"] == "auto"
    done(stack, step_two["id"])
    assert len(stack.fakes.sent()) == 3


def test_bounce_blocks_declared_steps(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {"key": "bump-1", "after_days": 1, "subject": "One", "text": "One"},
            {"key": "bump-2", "after_days": 2, "subject": "Two", "text": "Two"},
        ],
    )
    batch = submit(stack, document, "bounce.json")
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    deliver_dsn(
        stack.fakes,
        to_address=account_address(stack, account),
        recipient="person1@example.com",
        original_message_id=initial["message_id"],
    )
    sync_and_wait(stack, account, 1)
    age_jobs(stack, [initial["id"]], 3)

    until(
        lambda: any(
            item["reason"] == "bounced"
            for item in events(stack).get("followup.skipped", [])
        )
    )
    assert batches(stack, batch["id"]) == []


def test_reply_cancels_an_already_derived_step(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
        followups=[
            {"key": "bump-1", "after_days": 1, "subject": "One", "text": "One"},
            {
                "key": "bump-2",
                "after_days": 1,
                "subject": "Two",
                "text": "Two",
                "require_approval": True,
            },
        ],
    )
    batch = submit(stack, document, "cancel.json")
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    age_jobs(stack, [initial["id"]], 2)

    step_one = step(stack, batch["id"], "bump-1")
    done(stack, step_one["id"])
    bump_one = job(step_one, "person1@example.com")
    age_jobs(stack, [bump_one["id"]], 2)
    step_two = step(stack, batch["id"], "bump-2")
    assert step_two["state"] == "awaiting_approval"

    reply(
        stack,
        account,
        from_address="person1@example.com",
        subject="Re: One",
        in_reply_to=bump_one["message_id"],
        references=(initial["message_id"], bump_one["message_id"]),
        expected=1,
    )
    wait_state(stack, step_two["id"], "person1@example.com", "cancelled")
    until(
        lambda: stack.api.get(f"/api/batches/{step_two['id']}")["state"] == "cancelled"
    )
    assert len(stack.fakes.sent()) == 2


def test_followup_inherits_the_parent_job_account(stack_factory) -> None:
    stack = stack_factory(
        accounts=["alice@local.test", "bob@local.test"],
        config_extra=dispatch_config(daily_allowance=10),
    )
    alice, bob = stack.accounts
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": alice},
        followups=[{"key": "bump-1", "after_days": 1, "subject": "One", "text": "One"}],
    )
    batch = submit(stack, document, "accounts.json")
    done(stack, batch["id"])
    initial = recipient_job(batch, "person1@example.com")
    assert initial["account_id"] == alice
    age_jobs(stack, [initial["id"]], 2)

    step_one = step(stack, batch["id"], "bump-1")
    done(stack, step_one["id"])
    item = job(step_one, "person1@example.com")
    assert item["account_id"] == alice
    assert item["account_id"] != bob
    sent(stack, item["message_id"])


def test_followups_outlook_lists_upcoming_steps(stack_factory) -> None:
    from tests.harness.inbound import cli_json

    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = submit(
        stack,
        campaign_of(
            2,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump-1",
                    "after_days": 5,
                    "subject": "Bump one",
                    "text": "Bump one body",
                }
            ],
        ),
        "outlook.json",
    )
    done(stack, batch["id"])

    outlook = stack.api.get("/api/followups/outlook?due=7d")
    items = outlook["items"]
    assert any(
        item["batch_id"] == batch["id"]
        and item["step"] == "bump-1"
        and item["next_due_at"]
        for item in items
    )

    listed = cli_json(stack, "followups", "due", "--due", "7d", "--json")
    assert any(
        item["batch_id"] == batch["id"] and item["step"] == "bump-1"
        for item in listed["items"]
    )


def test_batch_thread_shows_steps_and_recipient_chain(stack_factory) -> None:
    from tests.harness.inbound import cli_json

    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    account = stack.accounts[0]
    batch = submit(
        stack,
        campaign_of(
            2,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump-1",
                    "after_days": 1,
                    "subject": "Bump one",
                    "text": "Bump one body",
                }
            ],
        ),
        "thread.json",
    )
    done(stack, batch["id"])
    first = recipient_job(batch, "person1@example.com")
    second = recipient_job(batch, "person2@example.com")

    reply(
        stack,
        account,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        in_reply_to=first["message_id"],
        references=(first["message_id"],),
        expected=1,
    )
    age_jobs(stack, [first["id"], second["id"]], 3)
    step_one = step(stack, batch["id"], "bump-1")
    done(stack, step_one["id"])

    payload = stack.api.get(f"/api/batches/{batch['id']}/thread")
    assert payload["batch"]["id"] == batch["id"]
    assert any(item["step"] == "bump-1" for item in payload["steps"])

    chain = stack.api.get(
        f"/api/batches/{batch['id']}/thread?recipient=person1@example.com"
    )
    recipient = chain["recipient"]
    assert recipient["recipient"] == "person1@example.com"
    assert recipient["jobs"]
    assert recipient["thread"] is not None
    assert recipient["thread"]["messages"]

    listed = cli_json(stack, "batch", "thread", batch["id"], "--json")
    assert listed["batch"]["id"] == batch["id"]
