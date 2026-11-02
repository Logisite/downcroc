from __future__ import annotations

import sys
import time

from downcroc.cli import paths as path_tools
from downcroc.cli.client import get, post
from downcroc.cli.commands import oauth_setup
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui

MAX_ATTEMPTS = 3
DEFAULT_WAIT_S = 300.0
_ATTEMPT_FAILED = {"failed", "cancelled", "expired"}


def password(args: object, ui: Ui, *, flag: str = "--password-stdin") -> str:
    path = getattr(args, "password_file", None)
    if path:
        return path_tools.read_secret(path)
    if getattr(args, "password_stdin", False):
        return path_tools.read_secret_stdin()
    if not sys.stdin.isatty():
        raise no_terminal(flag)
    return prompts.ask_secret("App password", ui=ui, flag=flag)


def wait(
    client,
    account_id: str,
    timeout: float | None,
    attempt_id: str | None = None,
) -> dict:
    """Wait for an OAuth attempt without crashing when no timeout was given.

    ``args.timeout`` is ``None`` for commands that inherit the root parser's
    default. Treat that as the documented default wait instead of doing
    arithmetic on ``None``.
    """
    budget = DEFAULT_WAIT_S if timeout is None else float(timeout)
    if budget <= 0:
        budget = DEFAULT_WAIT_S
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if attempt_id:
            attempt = get(client, f"/api/attempts/{attempt_id}")
            state = attempt.get("state")
            if state in _ATTEMPT_FAILED:
                raise CliError(
                    f"the sign-in attempt ended as {state}",
                    code=f"oauth_{state}",
                    hint="run `downcroc account connect` again",
                )
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
    if not ui.json_mode:
        print(
            ui.paint(
                "app password: one SMTP seat, roughly 5 messages in 2-6 minutes "
                "at default pacing, and Gmail may throttle the mailbox. OAuth is "
                "recommended because it adds API lanes and avoids the SMTP "
                "firewall.",
                "warn",
            ),
            file=sys.stderr,
        )
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
    if ui.interactive:
        from downcroc.cli.commands import oauth_wizard

        return oauth_wizard.run(
            client,
            account,
            ui,
            timeout=getattr(args, "timeout", None),
        )
    params = {}
    if getattr(args, "client", None):
        params["client_id"] = args.client
    if getattr(args, "transport", None):
        params["transport"] = args.transport
    attempt = post(client, f"/api/accounts/{account['id']}/attempts", **params)
    if not ui.json_mode:
        print(f"open {attempt['authorization_url']}", file=sys.stderr)
        print(
            f"the link expires at {attempt['expires_at']}",
            file=sys.stderr,
        )
    redirect = getattr(args, "redirect_url", None)
    if redirect:
        oauth_setup.deliver_redirect(redirect)
    account = wait(
        client,
        account["id"],
        getattr(args, "timeout", None),
        attempt.get("id"),
    )
    if account["status"] != "connected":
        raise CliError(
            "the browser sign-in did not finish",
            code="oauth_incomplete",
            hint="run downcroc account connect again",
        )
    return account
