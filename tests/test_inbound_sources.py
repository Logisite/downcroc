from __future__ import annotations

from datetime import UTC, datetime

from tests.conftest import Stack
from tests.harness.gmail import FakeGmail
from tests.harness.inbound import (
    cli as _cli,
)
from tests.harness.inbound import (
    cli_data as _data,
)
from tests.harness.inbound import (
    cli_json as _json,
)
from tests.harness.inbound import (
    inbound_config as _inbound_config,
)
from tests.harness.inbound import (
    oauth_account as _oauth_account,
)
from tests.harness.inbound import (
    raw_message as _raw,
)
from tests.harness.inbound import (
    until as _until,
)


def _messages(stack: Stack, account_id: str) -> list[dict]:
    return _json(
        stack,
        "mail",
        "list",
        "--account",
        account_id,
        "--json",
    )


def _row(stack: Stack, account_id: str) -> dict:
    return next(
        item
        for item in _data(stack, "doctor", "inbound", "--json")["accounts"]
        if item["account_id"] == account_id
    )


def test_cli_auto_uses_imap_for_password_accounts(stack_factory) -> None:
    stack = stack_factory(config_extra=_inbound_config())
    account_id = stack.accounts[0]

    body = _data(stack, "doctor", "inbound", "--json")
    assert body["sources"] == {"imap": 2, "gmail_api": 0}
    assert all(row["owner"] == "imap" for row in body["accounts"])

    refused = _cli(
        stack,
        "account",
        "inbound",
        account_id,
        "--source",
        "gmail_api",
        "--json",
    )
    assert refused.returncode != 0
    assert "gmail api" in refused.stdout.lower() + refused.stderr.lower()

    changed = _json(
        stack,
        "account",
        "inbound",
        account_id,
        "--source",
        "auto",
        "--json",
    )
    assert changed["inbound"]["override"] is None


def test_cli_gmail_api_owner_backfills_and_syncs_history(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack = stack_factory(
            config_extra=_inbound_config(),
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        account_id = _oauth_account(stack, gmail)
        gmail.add(_raw("first@example.test", subject="First"))
        gmail.add(_raw("sent@example.test", subject="Sent"), labels=("SENT",))

        kinds = {
            item["kind"]
            for item in _json(
                stack,
                "account",
                "transport",
                "list",
                account_id,
                "--json",
            )
        }
        assert kinds == {"smtp", "gmail_api"}

        switched = _json(
            stack,
            "account",
            "inbound",
            account_id,
            "--source",
            "gmail_api",
            "--json",
        )
        assert switched["inbound"]["override"] == "gmail_api"

        _until(
            lambda: (
                _row(stack, account_id)["cursor_source"] == "gmail_api"
                and len(_messages(stack, account_id)) == 1
            ),
            timeout=45.0,
        )
        assert [item["message_id"] for item in _messages(stack, account_id)] == [
            "first@example.test"
        ]
        row = _row(stack, account_id)
        assert row["owner"] == "gmail_api"
        assert row["history_id"]
        first_history = row["history_id"]

        gmail.add(_raw("second@example.test", subject="Second"))
        _json(stack, "account", "sync", account_id, "--json")
        _until(lambda: len(_messages(stack, account_id)) == 2, timeout=45.0)

        row = _row(stack, account_id)
        assert int(row["history_id"]) > int(first_history)
    finally:
        gmail.stop()


def test_cli_expired_history_resyncs_without_duplicates(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack = stack_factory(
            config_extra=_inbound_config(),
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        account_id = _oauth_account(stack, gmail)
        gmail.add(_raw("first@example.test", subject="First"))
        _json(
            stack,
            "account",
            "inbound",
            account_id,
            "--source",
            "gmail_api",
            "--json",
        )
        _until(
            lambda: (
                _row(stack, account_id)["cursor_source"] == "gmail_api"
                and len(_messages(stack, account_id)) == 1
            ),
            timeout=45.0,
        )

        gmail.expire_history()
        gmail.add(_raw("second@example.test", subject="Second"))
        _json(stack, "account", "sync", account_id, "--json")
        _until(lambda: len(_messages(stack, account_id)) == 2, timeout=45.0)

        stored = _messages(stack, account_id)
        assert len(stored) == 2
        assert {item["message_id"] for item in stored} == {
            "first@example.test",
            "second@example.test",
        }
    finally:
        gmail.stop()


def test_cli_sweep_stays_in_the_inbox(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack = stack_factory(
            config_extra=_inbound_config(),
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        account_id = _oauth_account(stack, gmail)
        gmail.add(_raw("inbox@example.test", subject="Inbox"))
        gmail.add(
            _raw("archived@example.test", subject="Archived"),
            labels=("IMPORTANT",),
        )
        gmail.add(
            _raw("sent@example.test", subject="Sent copy"),
            labels=("SENT",),
        )

        body = _data(stack, "doctor", "inbound", "--json")
        row = next(
            item for item in body["accounts"] if item["account_id"] == account_id
        )
        assert row["owner"] == "imap"

        _until(lambda: len(_messages(stack, account_id)) == 1, timeout=60.0)
        stored = _messages(stack, account_id)
        assert [item["message_id"] for item in stored] == ["inbox@example.test"]

        after = _data(stack, "doctor", "inbound", "--json")
        row = next(
            item for item in after["accounts"] if item["account_id"] == account_id
        )
        assert row["owner"] == "imap"
        assert row["cursor_source"] == "imap"
        assert row["last_sweep_at"]
        swept_at = row["last_sweep_at"]

        stack.daemon.stop()
        stack.daemon.start(stack.fakes, preserve_config=True)

        again = _row(stack, account_id)
        assert again["last_sweep_at"] == swept_at
        assert [item["message_id"] for item in _messages(stack, account_id)] == [
            "inbox@example.test"
        ]
    finally:
        gmail.stop()


def test_cli_idle_cap_falls_back_and_reports(stack_factory) -> None:
    provider = (
        "\n[providers.idle]\n"
        'label = "Idle test"\n'
        'imap_host = "{host}"\n'
        "imap_port = {imap_port}\n"
        'imap_tls = "none"\n'
        'smtp_host = "{host}"\n'
        "smtp_port = {smtp_port}\n"
        'smtp_tls = "none"\n'
        'auth_kind = "app_password"\n'
        'smtp_auth_mechanism = "PLAIN"\n'
        'sent_folder = "Sent"\n'
        "supports_idle = true\n"
        "requires_user_agent = false\n"
        "attachment_max_bytes = 26214400\n"
    )

    def providers(fakes) -> str:
        return provider.format(
            host=fakes.host,
            imap_port=fakes.imap_port,
            smtp_port=fakes.smtp_port,
        )

    stack = stack_factory(
        config_extra=_inbound_config(idle_fleet_cap=1),
        accounts=[],
        extra_providers=providers,
    )
    ids = []
    for address in ("idle-one@local.test", "idle-two@local.test"):
        account = _json(
            stack,
            "account",
            "add",
            "--provider",
            "idle",
            "--address",
            address,
            "--json",
        )
        _json(
            stack,
            "account",
            "connect",
            account["id"],
            "--password-stdin",
            "--json",
            stdin="app-password\n",
        )
        ids.append(account["id"])

    def settled() -> bool:
        rows = _data(stack, "doctor", "inbound", "--json")["accounts"]
        chosen = [row for row in rows if row["account_id"] in ids]
        return (
            len(chosen) == 2
            and all(row["status"] == "connected" for row in chosen)
            and any(row["mode"] == "imap_poll" for row in chosen)
        )

    _until(settled, timeout=45.0)

    body = _data(stack, "doctor", "inbound", "--json")
    rows = {
        row["account_id"]: row for row in body["accounts"] if row["account_id"] in ids
    }
    assert body["idle_fleet_cap"] == 1
    denied = [row for row in rows.values() if not row["idle_allowed"]]
    allowed = [row for row in rows.values() if row["idle_allowed"]]
    assert len(denied) == 1
    assert denied[0]["mode"] == "imap_poll"
    assert len(allowed) == 1
    assert allowed[0]["mode"] in {"idle", "reconnecting"}


def test_gmail_backfill_respects_ingest_since_init(stack_factory) -> None:
    gmail = FakeGmail().start()
    gmail.add(
        _raw(
            "old@example.test",
            subject="Old",
            date=datetime(2020, 1, 1, tzinfo=UTC),
        ),
        labels=("INBOX",),
    )
    try:
        stack = stack_factory(
            config_extra=_inbound_config(ingest_since_init=True),
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        account_id = _oauth_account(stack, gmail)
        gmail.add(_raw("new@example.test", subject="New"))
        _json(
            stack,
            "account",
            "inbound",
            account_id,
            "--source",
            "gmail_api",
            "--json",
        )
        _until(lambda: len(_messages(stack, account_id)) == 1, timeout=45.0)
        assert [item["message_id"] for item in _messages(stack, account_id)] == [
            "new@example.test"
        ]
    finally:
        gmail.stop()
