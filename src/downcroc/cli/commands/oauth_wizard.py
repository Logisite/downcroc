from __future__ import annotations

import webbrowser

from downcroc.cli.client import get, post
from downcroc.cli.commands import oauth_setup
from downcroc.cli.commands.account_connect import wait
from downcroc.cli.errors import CliError
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def run(client, account: dict, ui: Ui, *, timeout: float | None = None) -> dict:
    provider = get(client, f"/api/providers/{account['provider']}")
    if not provider["ready"]:
        oauth_setup.import_client(ui, account["provider"])
        provider = get(client, f"/api/providers/{account['provider']}")
    project = oauth_setup.project_id(client, account["provider"])
    _route_card(ui)
    oauth_setup.enable_gmail_api(ui, project)
    oauth_setup.warnings(ui)
    if not prompts.confirm("Continue to the Google sign-in page?", ui=ui, default=True):
        raise CliError("cancelled", code="cancelled")

    attempt = post(client, f"/api/accounts/{account['id']}/attempts")
    print()
    print(f"Open this URL:\n  {attempt['authorization_url']}")
    print(f"It expires at {attempt['expires_at']}")
    if ui.interactive:
        webbrowser.open(attempt["authorization_url"])
    pasted = prompts.ask(
        "Paste the full redirect URL, or press Enter to wait",
        ui=ui,
        required=False,
        field="redirect URL",
    )
    if pasted.strip():
        oauth_setup.deliver_redirect(pasted.strip())

    try:
        result = wait(client, account["id"], timeout or 300.0, attempt.get("id"))
    except CliError as error:
        if not _retry_api_check(client, account, ui):
            raise CliError(error.label, code=error.code, hint=error.hint) from error
        result = get(client, f"/api/accounts/{account['id']}")
    _offer_smtp(result, client, ui)
    return result


def _route_card(ui: Ui) -> None:
    print()
    print("Gmail API route")
    print("  Adds HTTPS API lanes plus an SMTP seat over OAuth.")
    print("  Recommended for batches: a single app-password seat sends about")
    print("  5 messages in 2-6 minutes at default pacing.")


def _retry_api_check(client, account: dict, ui: Ui) -> bool:
    if not ui.interactive:
        return False
    if not prompts.confirm(
        "Retry the Gmail API check without repeating OAuth?",
        ui=ui,
        default=True,
    ):
        return False
    try:
        post(client, f"/api/accounts/{account['id']}/verify", None, refresh="true")
    except CliError as error:
        print(ui.result(False, error.label))
        if error.hint:
            print(f"  {error.hint}")
        return False
    return True


def _offer_smtp(account: dict, client, ui: Ui) -> None:
    if not ui.interactive:
        return
    print()
    print("OAuth also provisioned the SMTP seat.")
    print("  The API lanes scale; the SMTP seat is the stable fallback.")
    print("  An app password is not needed for this mailbox.")
