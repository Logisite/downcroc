from __future__ import annotations

from tests.conftest import Stack
from tests.harness.dispatch import dispatch_config
from tests.harness.gmail import FakeGmail
from tests.harness.logs import events
from tests.outbound.test_provider_quota import _gmail_account


def _send(stack: Stack, account_id: str) -> dict:
    job = stack.api.post(
        "/api/jobs",
        {
            "account_id": account_id,
            "recipient": "person@example.com",
            "subject": "Logging",
            "text": "Body",
        },
    )
    return stack.api.post(f"/api/jobs/{job['id']}/send")


def test_smtp_send_names_account_transport_and_binding(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    sent = _send(stack, alice)
    assert sent["state"] == "sent"

    binding = next(
        item
        for item in stack.api.get(f"/api/accounts/{alice}/transports")
        if item["kind"] == "smtp"
    )
    found = events(stack)
    job_sent = found["job.sent"][-1]
    assert job_sent["account"] == alice
    assert job_sent["transport"] == "smtp"
    assert job_sent["binding"] == binding["id"]
    accepted = found["smtp.accepted"][-1]
    assert accepted["account"] == alice
    assert accepted["binding"] == binding["id"]
    assert accepted["transport"] == "smtp"
    attempt = found["transport.attempt"][-1]
    assert attempt["job"] == sent["id"]
    assert attempt["binding"] == binding["id"]


def test_gmail_send_names_transport_and_binding(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account = _gmail_account(stack_factory, gmail)
        sent = _send(stack, account)
        assert sent["state"] == "sent"
        binding = next(
            item
            for item in stack.api.get(f"/api/accounts/{account}/transports")
            if item["kind"] == "gmail_api"
        )
        found = events(stack)
        accepted = found["gmail.accepted"][-1]
        assert accepted["transport"] == "gmail_api"
        assert accepted["binding"] == binding["id"]
        assert found["job.sent"][-1]["transport"] == "gmail_api"
    finally:
        gmail.stop()
