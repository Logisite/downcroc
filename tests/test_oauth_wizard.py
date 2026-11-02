from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from tests.conftest import Stack
from tests.harness.gmail import FakeGmail
from tests.harness.inbound import cli_json
from tests.harness.pty import Session

ANSI = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]")
DOWN = b"\x1b[B"


def _client_file(stack: Stack, gmail: FakeGmail) -> Path:
    path = stack.root / "oauth-client.json"
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client",
                    "client_secret": "test-secret",
                    "auth_uri": f"{gmail.base_url}/authorize",
                    "token_uri": f"{gmail.base_url}/token",
                    "redirect_uris": ["http://127.0.0.1"],
                    "project_id": "test-project",
                }
            }
        )
    )
    return path


def _pending_account(stack: Stack) -> str:
    account = cli_json(
        stack,
        "account",
        "add",
        "--provider",
        "gmail",
        "--address",
        "gmail@local.test",
        "--json",
    )
    return account["id"]


def _url(session: Session) -> str:
    text = ANSI.sub(b"", session.raw).decode("utf-8", "replace")
    found = re.search(r"http://[^\s]+/authorize\?[^\s]+", text)
    assert found, text
    return found.group(0).rstrip("\r\n")


def _redirect(url: str) -> None:
    query = parse_qs(urlparse(url).query)
    redirect = query["redirect_uri"][0]
    state = query["state"][0]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(
        f"{redirect}?{urlencode({'code': 'test-code', 'state': state})}",
        timeout=30,
    ) as response:
        response.read()


def _step(session: Session, needle: bytes, keys: bytes = b"\r") -> None:
    session.wait_for(needle)
    session.raw = b""
    session.write(keys)


def _ready(
    stack_factory, gmail: FakeGmail, *, client: bool = True
) -> tuple[Stack, str]:
    stack = stack_factory(
        accounts=[],
        extra_providers=lambda fakes: gmail.provider_toml(fakes, client=client),
    )
    return stack, _pending_account(stack)


def test_connect_wizard_runs_each_card_and_keeps_smtp(stack_factory) -> None:
    os.environ["BROWSER"] = "true"
    gmail = FakeGmail().start()
    try:
        stack, account_id = _ready(stack_factory, gmail)
        client = _client_file(stack, gmail)
        cli_json(
            stack,
            "provider",
            "credentials",
            "set",
            "gmail",
            "--client",
            str(client),
            "--json",
        )
        session = Session(stack, "account", "connect", account_id, width=100)
        try:
            _step(session, b"Gmail OAuth route")
            _step(session, b"I enabled the Gmail API")
            _step(session, b"Continue to Google sign-in")
            session.wait_for(b"Open this URL")
            _redirect(_url(session))
            session.raw = b""
            session.write(b"\r")
            session.wait_for(b"SMTP over OAuth is already provisioned", timeout=90)
            assert session.process.wait(timeout=30) == 0
        finally:
            session.close()
        account = cli_json(stack, "account", "show", account_id, "--json")
        assert account["status"] == "connected"
    finally:
        gmail.stop()


def test_connect_wizard_goes_back_and_cancels(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account_id = _ready(stack_factory, gmail)
        client = _client_file(stack, gmail)
        cli_json(
            stack,
            "provider",
            "credentials",
            "set",
            "gmail",
            "--client",
            str(client),
            "--json",
        )
        session = Session(stack, "account", "connect", account_id, width=100)
        try:
            _step(session, b"Gmail OAuth route")
            _step(session, b"I enabled the Gmail API", DOWN + DOWN + b"\r")
            _step(session, b"Gmail OAuth route", DOWN + b"\r")
            assert session.process.wait(timeout=30) == 1
        finally:
            session.close()
        account = cli_json(stack, "account", "show", account_id, "--json")
        assert account["status"] == "pending"
    finally:
        gmail.stop()


def test_connect_wizard_reports_invalid_client_json(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack, account_id = _ready(stack_factory, gmail, client=False)
        bad = stack.root / "bad-client.json"
        bad.write_text("{}")
        session = Session(stack, "account", "connect", account_id, width=100)
        try:
            _step(session, b"Gmail OAuth route")
            _step(session, b"Import the client JSON")
            _step(session, b"Client JSON path", str(bad).encode() + b"\r")
            session.wait_for(b"not a Google OAuth client", timeout=30)
            session.raw = b""
            session.write(b"\r")
            session.wait_for(b"Gmail OAuth route")
            session.raw = b""
            session.write(DOWN + b"\r")
            assert session.process.wait(timeout=30) == 1
        finally:
            session.close()
        account = cli_json(stack, "account", "show", account_id, "--json")
        assert account["status"] == "pending"
    finally:
        gmail.stop()
