from __future__ import annotations

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.followups import age_jobs, done, job, recipient_job, step
from tests.harness.gmail import FakeGmail
from tests.harness.logs import events
from tests.harness.seed import until
from tests.outbound.test_provider_quota import _gmail_account

FAST = (
    "\n[backfill]\n"
    "startup_delay_s = 0.5\n"
    "recheck_s = 0.5\n"
    "pass_cooldown_s = 0.5\n"
    "jitter_s = 0.0\n"
    "jitter_max_s = 0.0\n"
    "imap_min_holes = 1\n"
)
ZERO_DAYS = FAST + "retry_after_days = 0\nsettle_s = 0\n"
SLOW_START = FAST.replace("startup_delay_s = 0.5", "startup_delay_s = 3.0")
DELAYED = "\n[backfill]\nstartup_delay_s = 3600\nrecheck_s = 3600\n"
DISABLED = "\n[backfill]\nenabled = false\n"


def _send_jobs(stack: Stack, account: str, count: int) -> list[dict]:
    jobs = []
    for index in range(count):
        created = stack.api.post(
            "/api/jobs",
            {
                "account_id": account,
                "recipient": f"person{index}@example.com",
                "subject": f"Backfill {index}",
                "text": "Body",
            },
        )
        sent = stack.api.post(f"/api/jobs/{created['id']}/send")
        assert sent["state"] == "sent", sent
        jobs.append(created)
    return jobs


def _attempt(stack: Stack, job_id: str) -> dict:
    rows = stack.api.get(f"/api/jobs/{job_id}/attempts")
    assert len(rows) == 1, rows
    return rows[0]


def _resolved(stack: Stack, job_id: str) -> list[dict]:
    return [
        item
        for item in events(stack).get("backfill.resolved", [])
        if item["job"] == job_id
    ]


def _wait_thread(stack: Stack, job_id: str) -> None:
    def resolved() -> bool:
        return bool(_attempt(stack, job_id)["provider_thread_id"])

    until(resolved)


def _gmail_stack(
    stack_factory, gmail: FakeGmail, config_extra: str
) -> tuple[Stack, str]:
    stack, account = _gmail_account(stack_factory, gmail, config_extra=config_extra)
    gmail.sent_sink = stack.fakes.deliver_sent
    gmail.sent_unsink = stack.fakes.delete_sent
    return stack, account


def test_backfill_recovers_thread_ids_over_imap(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, FAST)
        jobs = _send_jobs(stack, account, 3)
        for created in jobs:
            assert _attempt(stack, created["id"])["provider_thread_id"] is None
        for created in jobs:
            _wait_thread(stack, created["id"])
        for created in jobs:
            row = _attempt(stack, created["id"])
            assert row["provider_thread_id"] == gmail.thread_of(created["message_id"])
            medium = _resolved(stack, created["id"])[-1]["medium"]
            assert medium == "imap"
    finally:
        gmail.stop()


def test_backfill_falls_back_to_api_search_without_extensions(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, FAST)
        stack.fakes.set_gm_extensions(False)
        jobs = _send_jobs(stack, account, 2)
        for created in jobs:
            _wait_thread(stack, created["id"])
        for created in jobs:
            row = _attempt(stack, created["id"])
            assert row["provider_thread_id"] == gmail.thread_of(created["message_id"])
            medium = _resolved(stack, created["id"])[-1]["medium"]
            assert medium == "api"
    finally:
        gmail.stop()


def test_backfill_marks_holes_missing_after_strikes(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, ZERO_DAYS)
        created = _send_jobs(stack, account, 1)[0]
        assert gmail.delete(created["message_id"])
        until(lambda: events(stack).get("backfill.missing"))
        missing = events(stack)["backfill.missing"][-1]
        row = _attempt(stack, created["id"])
        assert missing["attempt"] == row["id"]
        assert row["provider_thread_id"] is None
        assert not _resolved(stack, created["id"])
    finally:
        gmail.stop()


def test_backfill_leaves_duplicate_message_ids_ambiguous(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, SLOW_START)
        created = _send_jobs(stack, account, 1)[0]
        duplicate = (
            b"From: Gmail <gmail@local.test>\r\n"
            b"To: person@example.com\r\n"
            b"Subject: Backfill 0\r\n"
            b"Message-ID: <" + created["message_id"].encode() + b">\r\n"
            b"\r\ncopy\r\n"
        )
        gmail.add(duplicate, labels=("SENT",))
        stack.fakes.deliver_sent("gmail@local.test", duplicate, 999)
        until(lambda: events(stack).get("backfill.ambiguous"))
        until(lambda: _attempt(stack, created["id"])["provider_thread_id"])
        row = _attempt(stack, created["id"])
        # The ambiguous RFC search writes nothing; the exact provider-id
        # lookup disambiguates and writes the true thread of the sent mail.
        assert row["provider_thread_id"] == gmail.thread_of(created["message_id"])
        medium = _resolved(stack, created["id"])[-1]["medium"]
        assert medium == "provider"
    finally:
        gmail.stop()


def test_all_media_share_one_hex_encoding(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account = _gmail_stack(stack_factory, gmail, FAST)
        # Medium 1: the API send response's threadId is stored verbatim.
        live = _send_jobs(stack, account, 1)[0]
        live_thread = _attempt(stack, live["id"])["provider_thread_id"]
        assert live_thread == gmail.thread_of(live["message_id"])
        assert live_thread == f"{int(live_thread, 16):x}"

        # Medium 4: the IMAP sweep fills an old hole with that same encoding.
        gmail.omit_thread_ids()
        old = _send_jobs(stack, account, 1)[0]
        _wait_thread(stack, old["id"])
        old_thread = _attempt(stack, old["id"])["provider_thread_id"]
        assert old_thread == gmail.thread_of(old["message_id"])
        assert old_thread == f"{int(old_thread, 16):x}"
    finally:
        gmail.stop()


def test_followup_send_uses_the_recovered_thread_id(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, FAST)
        document = campaign_of(
            1,
            options={"approval": "auto"},
            routing={"mode": "fixed", "account": account},
            followups=[
                {
                    "key": "bump-1",
                    "after_days": 1,
                    "subject": "Bump",
                    "text": "Bump body",
                }
            ],
        )
        batch = submit(stack, document, "backfill-thread.json")
        done(stack, batch["id"])
        first = recipient_job(batch, "person1@example.com")
        until(lambda: _attempt(stack, first["id"])["provider_thread_id"])
        recovered = _attempt(stack, first["id"])["provider_thread_id"]
        assert recovered == gmail.thread_of(first["message_id"])

        age_jobs(stack, [first["id"]], 3)
        bump_step = step(stack, batch["id"], "bump-1")
        done(stack, bump_step["id"])
        bump = job(bump_step, "person1@example.com")
        until(lambda: gmail.thread_of(bump["message_id"]))
        assert gmail.thread_of(bump["message_id"]) == recovered
    finally:
        gmail.stop()


def test_backfill_resumes_after_daemon_restart(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, DELAYED)
        jobs = _send_jobs(stack, account, 2)
        stack.daemon.stop()

        config = stack.daemon.config / "config.toml"
        text = config.read_text()
        config.write_text(
            text.replace("startup_delay_s = 3600", "startup_delay_s = 0.5").replace(
                "recheck_s = 3600", "recheck_s = 0.5"
            )
        )
        stack.daemon.start(stack.fakes, preserve_config=True)
        stack.api.unlock()
        for created in jobs:
            _wait_thread(stack, created["id"])
        for created in jobs:
            row = _attempt(stack, created["id"])
            assert row["provider_thread_id"] == gmail.thread_of(created["message_id"])
    finally:
        gmail.stop()


def test_backfill_disabled_leaves_holes_untouched(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        gmail.omit_thread_ids()
        stack, account = _gmail_stack(stack_factory, gmail, DISABLED)
        created = _send_jobs(stack, account, 1)[0]
        assert _attempt(stack, created["id"])["provider_thread_id"] is None
        assert not events(stack).get("backfill.started")
        assert not events(stack).get("backfill.resolved")
    finally:
        gmail.stop()
