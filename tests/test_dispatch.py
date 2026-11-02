from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from email.utils import parseaddr

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.daemon import free_port
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def test_jobs_drain_within_per_account_allowance(stack_factory) -> None:
    # SMTP is serial by design, so this checks allowance distribution across
    # mailboxes rather than fleet throughput.
    stack = stack_factory(
        config_extra=dispatch_config(
            daily_allowance=60,
            max_in_flight=4,
            global_in_flight=16,
        ),
        accounts=[
            "alice@local.test",
            "bob@local.test",
            "carol@local.test",
            "dave@local.test",
        ],
    )
    batch = submit(stack, campaign_of(200, options={"approval": "auto"}))

    _done(stack, batch["id"], timeout=240)

    sent = stack.fakes.sent()
    assert len(sent) == 200
    assert len({message["Message-ID"] for message in sent}) == 200
    counts: dict[str, int] = {}
    for message in sent:
        sender = parseaddr(message["From"])[1]
        counts[sender] = counts.get(sender, 0) + 1
    assert len(counts) == 4
    assert max(counts.values()) <= 60
    detail = stack.api.get(f"/api/batches/{batch['id']}")
    assert detail["counts"] == {
        "sent": 200,
        "inbound": 0,
        "replies": 0,
        "late_replies": 0,
        "bounces": 0,
    }


def test_nothing_sends_outside_the_window(stack_factory) -> None:
    hour = datetime.now().astimezone().hour
    start = (hour + 2) % 24
    end = start + 1
    if end == 24:
        end = 24
    stack = stack_factory(
        config_extra=dispatch_config(
            window_start=start,
            window_end=end,
            log_level="debug",
        )
    )
    batch = submit(stack, campaign_of(2, options={"approval": "auto"}))

    until(
        lambda: any(
            item["reason"] == "window closed"
            for item in events(stack).get("dispatch.idle", [])
        ),
        timeout=10,
    )
    assert stack.fakes.sent() == []
    assert stack.api.get(f"/api/batches/{batch['id']}")["state"] == "sending"


def test_kill_restart_loses_nothing_and_duplicates_nothing(stack_factory) -> None:
    config = dispatch_config(
        daily_allowance=1000,
        max_in_flight=4,
        tick_s=0.05,
    )
    stack = stack_factory(
        config_extra=config,
        accounts=["alice@local.test"],
    )
    batch = submit(stack, campaign_of(40, options={"approval": "auto"}))
    until(lambda: len(stack.fakes.sent()) >= 3, timeout=30)

    stack.daemon.kill()
    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()

    _done(stack, batch["id"], timeout=120)
    sent = stack.fakes.sent()
    assert len(sent) == 40
    assert len({message["Message-ID"] for message in sent}) == 40


def test_expired_lease_is_reclaimed(stack_factory) -> None:
    config = dispatch_config(
        daily_allowance=1000,
        max_in_flight=4,
        tick_s=0.05,
        lease_seconds=10,
    )
    stack = stack_factory(
        config_extra=config,
        accounts=["alice@local.test"],
    )
    batch = submit(stack, campaign_of(20, options={"approval": "auto"}))
    until(lambda: len(stack.fakes.sent()) >= 2, timeout=30)

    stack.daemon.kill()
    database = stack.daemon.data_home / "downcroc" / "downcroc.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "update jobs set lease_expires_at = '2000-01-01T00:00:00Z' "
            "where state = 'sending'"
        )
        connection.commit()
    providers = stack.daemon.config / "providers.toml"
    text = providers.read_text()
    text = text.replace(
        f"imap_port = {stack.fakes.imap_port}",
        f"imap_port = {free_port()}",
    )
    providers.write_text(text)

    stack.daemon.start(stack.fakes, config)
    stack.api.unlock()

    _done(stack, batch["id"], timeout=120)
    sent = stack.fakes.sent()
    assert len(sent) == 20
    assert len({message["Message-ID"] for message in sent}) == 20
