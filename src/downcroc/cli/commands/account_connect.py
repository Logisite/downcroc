from __future__ import annotations

import sys
import time

from downcroc.cli import paths as path_tools
from downcroc.cli.client import get, post
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui

MAX_ATTEMPTS = 3


def password(args: object, ui: Ui, *, flag: str = "--password-stdin") -> str:
    path = getattr(args, "password_file", None)
    if path:
        return path_tools.read_secret(path)
    if getattr(args, "password_stdin", False):
        return path_tools.read_secret_stdin()
    if not sys.stdin.isatty():
        raise no_terminal(flag)
    return prompts.ask_secret("App password", ui=ui, flag=flag)


def wait(client, account_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        account = get(client, f"/api/accounts/{account_id}")
        if account["status"] in {"connected", "needs_reauth"}:
            return account
        time.sleep(0.5)
    raise CliError(
        "timed out waiting for the account to connect",
        code="connect_timeout",
        hint="finish the browser sign-in, then run downcroc account verify",
    )


def connect_now(client, account: dict, args: object, ui: Ui) -> dict:
    provider = get(client, f"/api/providers/{account['provider']}")
    if provider["auth_kind"] == "oauth2":
        return _oauth(client, account, args, ui)
    if not provider["ready"]:
        raise CliError(
            "the provider is not ready",
            code="provider_not_ready",
            hint=f"run downcroc provider edit {provider['id']}",
            fields={"missing": ", ".join(provider["missing"])},
        )
    return _app_password(client, account, provider, args, ui)


def connected(account: dict, ui: Ui) -> None:
    if ui.json_mode:
        json_out(account)
        return
    record(
        {
            "account": f"{account['id']} {account['address']}",
            "status": account["status"],
            "watcher": "on" if account["watcher_enabled"] else "off",
        }
    )
    print(ui.result(True, "connected"))


def _app_password(client, account: dict, provider: dict, args: object, ui: Ui) -> dict:
    failures = 0
    endpoint = f"{provider['imap_host']}:{provider['imap_port']}"
    while True:
        secret = password(args, ui)
        if not ui.json_mode:
            print(f"checking {endpoint} ...", file=sys.stderr)
        started = time.monotonic()
        try:
            account = post(
                client,
                f"/api/accounts/{account['id']}/connect",
                {"password": secret},
            )
            if not ui.json_mode:
                elapsed = time.monotonic() - started
                print(f"  {elapsed:.1f}s", file=sys.stderr)
            return account
        except CliError as error:
            failures += 1
            if ui.json_mode:
                raise
            print(ui.result(False, error.label), file=sys.stderr)
            if error.hint:
                print(f"  hint: {error.hint}", file=sys.stderr)
            if failures >= MAX_ATTEMPTS:
                raise CliError(
                    f"still not connected after {MAX_ATTEMPTS} attempts",
                    code=error.code,
                    hint="the provider may lock the mailbox after repeated failures; "
                    "wait, then try `downcroc account connect` once",
                ) from error
            if not ui.interactive:
                raise
            choice = prompts.choose(
                "what next",
                [
                    prompts.Option("Retry", "retry", "enter the password again"),
                    prompts.Option("Stop", "stop", "leave the account pending"),
                ],
                ui=ui,
            )
            if choice != "retry":
                raise CliError("not connected, nothing was stored", code="cancelled")
        finally:
            args.password_stdin = False
            args.password_file = None


def _oauth(client, account: dict, args: object, ui: Ui) -> dict:
    params = {}
    if getattr(args, "client", None):
        params["client_id"] = args.client
    attempt = post(client, f"/api/accounts/{account['id']}/attempts", **params)
    if not ui.json_mode:
        print(f"open {attempt['authorization_url']}", file=sys.stderr)
        print(
            f"the link expires at {attempt['expires_at']}",
            file=sys.stderr,
        )
    account = wait(client, account["id"], args.timeout)
    if account["status"] != "connected":
        raise CliError(
            "the browser sign-in did not finish",
            code="oauth_incomplete",
            hint="run downcroc account connect again",
        )
    return account
