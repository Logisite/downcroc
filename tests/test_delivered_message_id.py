from __future__ import annotations

import sqlite3
from contextlib import closing

from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.followups import age_jobs, done, job, step
from tests.harness.gmail import FakeGmail
from tests.harness.logs import events
from tests.outbound.test_provider_quota import _gmail_account


def _db(stack):
    return stack.daemon.data_home / "downcroc" / "downcroc.db"


def _delivered_id(stack, job_id: str) -> str | None:
    with closing(sqlite3.connect(_db(stack))) as db:
        row = db.execute(
            "select delivered_message_id from jobs where id = ?", (job_id,)
        ).fetchone()
    return row[0] if row else None


def _set_delivered_id(stack, job_id: str, value: str | None) -> None:
    with closing(sqlite3.connect(_db(stack))) as db:
        db.execute(
            "update jobs set delivered_message_id = ? where id = ?", (value, job_id)
        )
        db.commit()


def _api_stack(stack_factory, gmail: FakeGmail):
    stack, account = _gmail_account(stack_factory, gmail)
    gmail.sent_sink = stack.fakes.deliver_sent
    return stack, account


def test_api_send_captures_gmail_delivered_id(stack_factory) -> None:
    """Gmail API send reads back and stores the real delivered Message-ID."""
    gmail = FakeGmail().start()
    try:
        gmail.overwrite_message_ids()
        stack, account = _api_stack(stack_factory, gmail)
        document = campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
        )
        batch = submit(stack, document, "capture.json")
        done(stack, batch["id"])

        job = batch["recipients"][0]
        delivered = _delivered_id(stack, job["id"])
        assert delivered is not None
        assert delivered.startswith("gmail")
        assert delivered != job["message_id"].strip("<>")

        captured = events(stack).get("followup.delivered_id_captured", [])
        row = next(item for item in captured if item["job"] == job["id"])
        assert row["source"] == "send_readback"
        assert row["minted"] == job["message_id"].strip("<>")
        assert row["delivered"] == delivered
    finally:
        gmail.stop()


def test_followup_references_gmail_delivered_id(stack_factory) -> None:
    """A followup built off an API parent references its delivered id."""
    gmail = FakeGmail().start()
    try:
        gmail.overwrite_message_ids()
        stack, account = _api_stack(stack_factory, gmail)
        document = campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump1",
                    "after_days": 1,
                    "when": "always",
                    "subject": "Re: Subject 1",
                    "text": "Followup body",
                }
            ],
        )
        batch = submit(stack, document, "parent.json")
        done(stack, batch["id"])
        parent_job = batch["recipients"][0]
        parent_delivered = _delivered_id(stack, parent_job["id"])
        age_jobs(stack, [parent_job["id"]], 3)

        step_batch = step(stack, batch["id"], "bump1")
        done(stack, step_batch["id"])
        child = job(step_batch, parent_job["recipient"])

        linked = events(stack).get("thread.linked", [])
        row = next(item for item in linked if item.get("child") == child["id"])
        assert row["reference_source"] == "delivered"
        assert row["in_reply_to"] == parent_delivered
        assert row["references_head"] == parent_delivered
        # The child itself had its delivered id captured on send.
        assert any(
            item["job"] == child["id"]
            for item in events(stack).get("followup.delivered_id_captured", [])
        )
    finally:
        gmail.stop()


def test_legacy_job_delivered_id_recovered_and_cached(stack_factory) -> None:
    """A legacy API job with NULL delivered id is recovered on demand and cached."""
    gmail = FakeGmail().start()
    try:
        gmail.overwrite_message_ids()
        stack, account = _api_stack(stack_factory, gmail)
        document = campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump1",
                    "after_days": 1,
                    "when": "always",
                    "subject": "Re: Subject 1",
                    "text": "Followup body",
                }
            ],
        )
        batch = submit(stack, document, "legacy.json")
        done(stack, batch["id"])
        parent_job = batch["recipients"][0]
        parent_delivered = _delivered_id(stack, parent_job["id"])
        assert parent_delivered is not None
        # Simulate a pre-fix legacy row: delivered id never stored.
        _set_delivered_id(stack, parent_job["id"], None)

        age_jobs(stack, [parent_job["id"]], 3)
        step_batch = step(stack, batch["id"], "bump1")
        done(stack, step_batch["id"])

        recovered = events(stack).get("followup.delivered_id_recovered", [])
        row = next(item for item in recovered if item["job"] == parent_job["id"])
        assert row["source"] == "opaque"
        assert row["delivered"] == parent_delivered
        assert _delivered_id(stack, parent_job["id"]) == parent_delivered
    finally:
        gmail.stop()


def test_recovery_failure_falls_back_to_minted(stack_factory) -> None:
    """If the parent message is gone, followup still builds with the minted id."""
    gmail = FakeGmail().start()
    try:
        gmail.overwrite_message_ids()
        stack, account = _api_stack(stack_factory, gmail)
        document = campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump1",
                    "after_days": 1,
                    "when": "always",
                    "subject": "Re: Subject 1",
                    "text": "Followup body",
                }
            ],
        )
        batch = submit(stack, document, "gone.json")
        done(stack, batch["id"])
        parent_job = batch["recipients"][0]
        minted = parent_job["message_id"].strip("<>")
        _set_delivered_id(stack, parent_job["id"], None)
        # Remove the parent message so both recovery paths fail.
        gmail.delete(minted)
        # The delivered (overwritten) id is stored under a gmail... value too.
        for msg in list(gmail._messages):
            if "mail.gmail.com" in (msg.message_id or ""):
                gmail._messages.remove(msg)

        age_jobs(stack, [parent_job["id"]], 3)
        step_batch = step(stack, batch["id"], "bump1")
        done(stack, step_batch["id"])

        failed = events(stack).get("followup.delivered_id_failed", [])
        assert any(item.get("job") == parent_job["id"] for item in failed)
        linked = events(stack).get("thread.linked", [])
        child = job(step_batch, parent_job["recipient"])
        row = next(item for item in linked if item.get("child") == child["id"])
        assert row["in_reply_to"] == minted
        assert row["reference_source"] == "minted_fallback"
    finally:
        gmail.stop()


def test_smtp_send_captures_minted_id(stack_factory) -> None:
    """SMTP send stores the minted id directly as the delivered id."""
    stack = stack_factory(accounts=["alice@local.test"], config_extra=dispatch_config())
    document = campaign_of(
        1,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": stack.accounts[0]},
    )
    batch = submit(stack, document, "smtp.json")
    done(stack, batch["id"])
    job = batch["recipients"][0]
    delivered = _delivered_id(stack, job["id"])
    assert delivered == job["message_id"].strip("<>")
    captured = events(stack).get("followup.delivered_id_captured", [])
    row = next(item for item in captured if item["job"] == job["id"])
    assert row["source"] == "smtp"
