from __future__ import annotations

import urllib.parse
import urllib.request

from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.gmail import FakeGmail
from tests.harness.logs import events
from tests.harness.seed import until


def test_sticky_smtp_seat_is_configurable_and_stable(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )

    first = stack.api.get("/api/doctor/capacity")
    assert len(first["smtp_active"]) == 1
    assert first["pinned_overflow"] == 0
    second = stack.api.get("/api/doctor/capacity")
    assert second["smtp_active"] == first["smtp_active"]

    status, body = stack.api.raw(
        "PATCH",
        "/api/config",
        {"dispatch": {"smtp_seat_sticky": False, "smtp_seat_max_s": 30}},
    )
    assert status == 200, body
    values = stack.api.get("/api/config")["config"]["dispatch"]
    assert values["smtp_seat_sticky"] is False
    assert values["smtp_seat_max_s"] == 30


def test_read_only_views_do_not_release_the_seat(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    first = stack.api.get("/api/doctor/capacity")
    active = first["smtp_active"]
    before = len(events(stack).get("dispatch.smtp_seat", []))

    for _ in range(3):
        stack.api.get("/api/doctor/capacity")
        stack.api.get("/api/batches")
        for account in stack.accounts:
            stack.api.get(f"/api/accounts/{account}")
            stack.api.get(f"/api/accounts/{account}/transports")

    after = events(stack).get("dispatch.smtp_seat", [])
    assert len(after) == before
    assert stack.api.get("/api/doctor/capacity")["smtp_active"] == active


def test_auto_routing_keeps_one_seat_until_the_batch_drains(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    stack.api.post("/api/service/pause", {"reason": "prepare unpin"})
    batch = submit(
        stack,
        campaign_of(6, options={"approval": "auto"}),
        "auto.json",
    )
    stack.api.post(
        "/api/jobs/reassign",
        {
            "job_ids": [job["id"] for job in batch["recipients"]],
            "unpin": True,
            "confirm": True,
        },
    )
    stack.api.post("/api/service/resume", {})
    until(lambda: stack.api.get(f"/api/batches/{batch['id']}")["state"] == "done")

    seats = events(stack).get("dispatch.smtp_seat", [])
    assert len(seats) <= 1
    assert all(item.get("reason") not in {"failover", "idle"} for item in seats)
    if seats:
        assert seats[0].get("source") == "dispatch"
        assert seats[0].get("sends", 0) >= 0


def _connect_gmail(stack, gmail: FakeGmail, address: str) -> str:
    account = stack.api.create_account(address, provider="gmail")
    attempt = stack.api.post(f"/api/accounts/{account['id']}/attempts")
    query = urllib.parse.parse_qs(
        urllib.parse.urlparse(attempt["authorization_url"]).query
    )
    redirect = query["redirect_uri"][0]
    state = query["state"][0]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(
        f"{redirect}?{urllib.parse.urlencode({'code': 'test-code', 'state': state})}",
        timeout=30,
    ) as response:
        response.read()
    until(
        lambda: stack.api.get(f"/api/attempts/{attempt['id']}")["state"] == "succeeded"
    )
    return account["id"]


def test_seat_moves_when_the_owner_has_no_work_left(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack = stack_factory(
            config_extra=dispatch_config(),
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        gmail.sent_sink = stack.fakes.deliver_sent
        first = _connect_gmail(stack, gmail, "one@gmail.test")
        second = _connect_gmail(stack, gmail, "two@gmail.test")
        initial = submit(
            stack,
            campaign_of(
                1,
                options={"approval": "auto"},
                routing={"mode": "fixed", "account": first},
            ),
            "initial.json",
        )
        until(lambda: stack.api.get(f"/api/batches/{initial['id']}")["state"] == "done")
        holder = stack.api.get("/api/doctor/capacity")["smtp_active"][0]
        worker = second if holder == first else first
        before = len(
            [
                item
                for item in events(stack).get("dispatch.smtp_seat", [])
                if item.get("source") == "dispatch"
            ]
        )

        stack.api.post("/api/service/pause", {"reason": "prepare api send"})
        batch = submit(
            stack,
            campaign_of(
                1,
                options={"approval": "auto"},
                routing={"mode": "fixed", "account": worker},
            ),
            "api.json",
        )
        stack.api.post("/api/service/resume", {})
        until(lambda: stack.api.get(f"/api/batches/{batch['id']}")["state"] == "done")

        assert stack.api.get("/api/doctor/capacity")["smtp_active"][0] == worker
        seats = [
            item
            for item in events(stack).get("dispatch.smtp_seat", [])
            if item.get("source") == "dispatch"
        ]
        assert len(seats) == before + 1
        assert seats[-1]["reason"] == "batch_drain"
        assert seats[-1]["released"] == holder
        sent = [
            item
            for item in events(stack).get("job.sent", [])
            if item.get("job") == batch["recipients"][0]["id"]
        ]
        assert len(sent) == 1
        assert sent[0]["transport"] == "smtp"
    finally:
        gmail.stop()


def test_archived_accounts_do_not_hold_a_seat(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test", "bob@local.test"],
    )
    alice, bob = stack.accounts
    stack.api.post(f"/api/accounts/{bob}/archive?confirm=true")

    plan = stack.api.get("/api/doctor/capacity")
    assert bob not in plan["smtp_active"]
    assert bob not in plan["smtp_queue"]
    assert alice in plan["smtp_queue"]
