from __future__ import annotations

import urllib.parse
import urllib.request

from downcroc.runtime.clock import utc_after
from tests.conftest import Stack
from tests.harness.dispatch import dispatch_config
from tests.harness.gmail import FakeGmail
from tests.harness.logs import events
from tests.harness.seed import until


def _create(stack: Stack, account_id: str, recipient: str) -> dict:
    status, job = stack.api.raw(
        "POST",
        "/api/jobs",
        {
            "account_id": account_id,
            "recipient": recipient,
            "subject": "Provider failure",
            "text": "Body",
        },
    )
    assert status == 201
    return job


def _send(stack: Stack, job: dict) -> tuple[int, dict]:
    return stack.api.raw("POST", f"/api/jobs/{job['id']}/send")


def _binding(stack: Stack, account_id: str, kind: str) -> dict:
    rows = stack.api.get(f"/api/accounts/{account_id}/transports")
    return next(item for item in rows if item["kind"] == kind)


def _reset(stack: Stack, account_id: str, binding: dict) -> None:
    stack.api.patch(
        f"/api/accounts/{account_id}/transports/{binding['id']}",
        {"enabled": False},
    )
    stack.api.patch(
        f"/api/accounts/{account_id}/transports/{binding['id']}",
        {"enabled": True},
    )


def test_smtp_classifies_enhanced_status_and_text(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    binding = _binding(stack, alice, "smtp")
    cases = [
        ("recipient@example.com", "550 5.1.1 no such user", "failed", "smtp_recipient"),
        (
            "full@example.com",
            "550 5.2.2 mailbox full",
            "retry_wait",
            "smtp_mailbox_full",
        ),
        ("temporary@example.com", "450 4.2.0 try later", "retry_wait", "smtp_450"),
        ("unknown@example.com", "550 context missing", "failed", "smtp_550"),
    ]
    for recipient, response, state, code in cases:
        stack.fakes.smtp_response(recipient, response)
        job = _create(stack, alice, recipient)
        status, sent = _send(stack, job)
        assert status == 200, sent
        assert sent["state"] == state
        assert sent["last_error"]["code"] == code
        _reset(stack, alice, binding)

    rejected = events(stack)["smtp.rejected"][-1]
    assert rejected["account"] == alice
    assert rejected["binding"]
    assert rejected["enhanced"] == "5.1.1" or rejected["enhanced"] is None


def test_smtp_quota_and_policy_change_binding_health(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=["alice@local.test"],
    )
    alice = stack.accounts[0]
    binding = _binding(stack, alice, "smtp")

    stack.fakes.smtp_response(
        "quota@example.com", "452 5.4.5 daily user sending limit exceeded"
    )
    job = _create(stack, alice, "quota@example.com")
    _, sent = _send(stack, job)
    assert sent["state"] == "retry_wait"
    assert sent["last_error"]["code"] == "smtp_quota"
    assert _binding(stack, alice, "smtp")["health"] == "quota_exhausted"
    quota = events(stack)["transport.quota"][-1]
    assert quota["account"] == alice
    assert quota["binding"] == binding["id"]
    assert quota["retry_s"] >= 1

    _reset(stack, alice, binding)
    stack.fakes.smtp_response("policy@example.com", "550 5.7.1 blocked by policy")
    job = _create(stack, alice, "policy@example.com")
    _, sent = _send(stack, job)
    assert sent["state"] == "failed"
    assert sent["last_error"]["code"] == "smtp_policy"
    assert _binding(stack, alice, "smtp")["health"] == "cooling_down"
    rejected = events(stack)["smtp.rejected"][-1]
    assert rejected["enhanced"] == "5.7.1"
    assert rejected["retryable"] is False
    updated = events(stack)["transport.binding_updated"][-1]
    assert updated["old"]["health"] != updated["new"]["health"]


def _gmail_account(stack_factory, gmail: FakeGmail) -> tuple[Stack, str]:
    stack = stack_factory(
        config_extra=dispatch_config(),
        accounts=[],
        extra_providers=lambda fakes: gmail.provider_toml(fakes),
    )
    account = stack.api.create_account("gmail@local.test", provider="gmail")
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
        lambda: stack.api.get(f"/api/attempts/{attempt['id']}")["state"] == "succeeded",
        timeout=60,
    )
    for binding in stack.api.get(f"/api/accounts/{account['id']}/transports"):
        if binding["kind"] == "smtp":
            stack.api.raw(
                "DELETE",
                f"/api/accounts/{account['id']}/transports/{binding['id']}?confirm=true",
            )
    return stack, account["id"]


def test_gmail_quota_reads_header_and_body_retry(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account = _gmail_account(stack_factory, gmail)
        binding = _binding(stack, account, "gmail_api")

        gmail.fail_send(
            403,
            {
                "error": {
                    "errors": [{"reason": "rateLimitExceeded"}],
                    "message": "slow down",
                }
            },
            {"Retry-After": "120"},
        )
        job = _create(stack, account, "person@example.com")
        _, sent = _send(stack, job)
        assert sent["state"] == "retry_wait"
        assert _binding(stack, account, "gmail_api")["health"] == "quota_exhausted"
        rejected = events(stack)["gmail.rejected"][-1]
        assert rejected["quota"] is True
        assert rejected["retry_after_s"] >= 120
        assert rejected["binding"] == binding["id"]

        _reset(stack, account, binding)
        retry_at = utc_after(300)
        gmail.fail_send(
            429,
            {
                "error": {
                    "errors": [{"reason": "userRateLimitExceeded"}],
                    "message": f"Retry after {retry_at}",
                }
            },
        )
        job = _create(stack, account, "second@example.com")
        _, sent = _send(stack, job)
        assert sent["state"] == "retry_wait"
        assert events(stack)["gmail.rejected"][-1]["retry_after_s"] >= 200
    finally:
        gmail.stop()


def test_gmail_auth_disabled_policy_and_server_errors(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account = _gmail_account(stack_factory, gmail)
        binding = _binding(stack, account, "gmail_api")

        gmail.fail_send(
            403,
            {
                "error": {
                    "errors": [{"reason": "accessNotConfigured"}],
                    "message": "off",
                }
            },
        )
        job = _create(stack, account, "disabled@example.com")
        _, sent = _send(stack, job)
        assert sent["state"] == "failed"
        assert _binding(stack, account, "gmail_api")["enabled"] is False
        _reset(stack, account, binding)

        gmail.fail_send(
            403,
            {"error": {"errors": [], "message": "domain policy blocks this sender"}},
        )
        job = _create(stack, account, "policy@example.com")
        _, sent = _send(stack, job)
        assert sent["state"] == "failed"
        assert _binding(stack, account, "gmail_api")["health"] == "cooling_down"
        _reset(stack, account, binding)

        gmail.fail_send(503, {"error": {"message": "backend unavailable"}})
        job = _create(stack, account, "uncertain@example.com")
        _, sent = _send(stack, job)
        assert sent["state"] == "sent_unconfirmed"

        gmail.fail_send(
            401,
            {
                "error": {
                    "errors": [{"reason": "authError"}],
                    "message": "invalid token",
                }
            },
        )
        job = _create(stack, account, "auth@example.com")
        status, body = _send(stack, job)
        assert status == 409
        assert body["error"] == "account_needs_reauth"
        assert stack.api.get(f"/api/accounts/{account}")["status"] == "needs_reauth"
    finally:
        gmail.stop()
