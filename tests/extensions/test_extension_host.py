from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.replies import (
    account_address,
    deliver_reply,
    messages,
    sync_and_wait,
)
from tests.harness.seed import until

SCRIPT = Path(__file__).parent / "fake_extension.py"


def _write_manifest(stack, capabilities: str = '"log"') -> None:
    directory = stack.daemon.config / "extensions"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fake.toml").write_text(
        "\n".join(
            [
                'id = "fake"',
                'name = "Fake extension"',
                'version = "1.0.0"',
                f"run = [{json.dumps(sys.executable)}, {json.dumps(str(SCRIPT))}]",
                'events = ["reply.attributed"]',
                f"capabilities = [{capabilities}]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_extension_runs_and_logs_without_credentials(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _write_manifest(stack)
    stack.api.post("/api/extensions/reload")
    stack.api.post("/api/extensions/fake/enable")

    rows = stack.api.get("/api/extensions")
    row = next(item for item in rows if item["id"] == "fake")
    assert row["enabled"] is True
    assert row["running"] is True

    result = stack.api.post(
        "/api/extensions/fake/test",
        {"event": "reply.attributed", "message": "msg_1"},
    )
    assert len(result) == 1
    assert result[0] == {"ok": True}

    logged = events(stack).get("extension.call", [])
    assert any(item.get("capability") == "log" for item in logged)
    assert not any("ENVLEAK" in str(item) for item in logged)


def test_extension_denies_ungranted_capability(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _write_manifest(stack)
    stack.api.post("/api/extensions/reload")
    stack.api.post("/api/extensions/fake/enable")

    result = stack.api.post(
        "/api/extensions/fake/test",
        {"event": "reply.attributed", "message": "msg_2", "reason": "deny"},
    )
    assert len(result) == 2
    assert result[1]["error"] == "CapabilityDenied"

    denied = events(stack).get("extension.denied", [])
    assert any(item.get("capability") == "mail.send" for item in denied)


def test_extension_can_reply_to_a_confirmed_reply(stack_factory) -> None:
    stack = stack_factory(config_extra=dispatch_config(), accounts=["alice@local.test"])
    account = stack.accounts[0]
    batch = submit(stack, campaign_of(1, options={"approval": "auto"}), "reply.json")
    until(lambda: stack.api.get(f"/api/batches/{batch['id']}")["state"] == "done")
    original = stack.api.get(f"/api/jobs?batch={batch['id']}")[0]

    deliver_reply(
        stack.fakes,
        to_address=account_address(stack, account),
        from_address="person@example.com",
        subject="Re: Subject 1",
        in_reply_to=original["message_id"],
    )
    sync_and_wait(stack, account, 1)
    until(
        lambda: any(
            item.get("reply_state") == "confirmed" for item in messages(stack, account)
        )
    )
    message = next(
        item
        for item in messages(stack, account)
        if item.get("reply_state") == "confirmed"
    )

    _write_manifest(stack, '"log", "mail.reply"')
    stack.api.post("/api/extensions/reload")
    stack.api.post("/api/extensions/fake/enable")
    before = len(events(stack).get("job.sent", []))

    result = stack.api.post(
        "/api/extensions/fake/test",
        {
            "event": "reply.attributed",
            "message": message["id"],
            "reason": "reply",
        },
    )
    assert result[0]["in_reply_to"] == original["id"]

    until(lambda: len(events(stack).get("job.sent", [])) == before + 1)
    sent = events(stack)["job.sent"][-1]
    reply_job = stack.api.get(f"/api/jobs/{result[0]['job']}")
    assert str(reply_job.get("subject", "")).startswith("Re:")
    assert sent.get("in_reply_to") == original["message_id"]
