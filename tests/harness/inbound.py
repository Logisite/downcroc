from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from tests.conftest import Stack
from tests.harness.gmail import FakeGmail

ROOT = Path(__file__).resolve().parents[2]


def cli(
    stack: Stack,
    *args: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def cli_json(stack: Stack, *args: str, stdin: str | None = None):
    result = cli(stack, *args, stdin=stdin)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def cli_data(stack: Stack, *args: str, stdin: str | None = None):
    """Read JSON even when a diagnostic command exits nonzero."""
    result = cli(stack, *args, stdin=stdin)
    if result.returncode != 0 and not result.stdout.strip():
        raise AssertionError(result.stderr or f"exit {result.returncode}")
    return json.loads(result.stdout)


def until(predicate, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError("condition was not met before the timeout")


def inbound_config(**values: object) -> str:
    defaults = {
        "source": "auto",
        "poll_interval_s": 5,
        "api_poll_s": 10,
        "sweep_tick_s": 10,
        "sweep_slot_jitter": 0.0,
        "sweep_accounts_per_tick": 1,
        "sweep_initial_days": 7,
        "sweep_limit": 50,
        "idle_fleet_cap": 20,
    }
    defaults.update(values)
    lines = ["", "[inbound]"]
    for key, value in defaults.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n"


def raw_message(
    message_id: str,
    subject: str = "Hello",
    body: str = "Body",
    sender: str = "sender@local.test",
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = f"<{message_id}>"
    message["From"] = f"Sender <{sender}>"
    message["To"] = "gmail@local.test"
    message["Subject"] = subject
    message.set_content(body)
    return message.as_bytes()


def oauth_account(
    stack: Stack,
    gmail: FakeGmail,
    address: str = "gmail@local.test",
) -> str:
    client = stack.root / "oauth-client.json"
    client.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client",
                    "client_secret": "test-secret",
                    "auth_uri": f"{gmail.base_url}/authorize",
                    "token_uri": f"{gmail.base_url}/token",
                    "redirect_uris": ["http://127.0.0.1"],
                }
            }
        )
    )
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
    account = cli_json(
        stack,
        "account",
        "add",
        "--provider",
        "gmail",
        "--address",
        address,
        "--json",
    )
    attempt = cli_json(stack, "account", "attempt", account["id"], "--json")
    url = urlparse(attempt["authorization_url"])
    query = parse_qs(url.query)
    redirect = query["redirect_uri"][0]
    state = query["state"][0]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(
        f"{redirect}?{urlencode({'code': 'test-code', 'state': state})}",
        timeout=30,
    ) as response:
        response.read()
    until(
        lambda: (
            cli_json(stack, "account", "show", account["id"], "--json")["status"]
            == "connected"
        ),
        timeout=45.0,
    )
    return account["id"]
