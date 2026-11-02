from __future__ import annotations

import webbrowser
from typing import Any

from downcroc.cli.client import delete, get, post
from downcroc.cli.commands import oauth_setup
from downcroc.cli.commands.account_connect import wait
from downcroc.cli.errors import CliError
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui

CANCELLED = CliError("cancelled", code="cancelled")


class _Session:
    def __init__(
        self,
        client: Any,
        account: dict,
        ui: Ui,
        timeout: float | None,
    ) -> None:
        self.client = client
        self.account = account
        self.ui = ui
        self.timeout = timeout
        self.attempt: dict | None = None


def run(client, account: dict, ui: Ui, *, timeout: float | None = None) -> dict:
    session = _Session(client, account, ui, timeout)
    step = "route"
    handlers = {
        "route": _route,
        "client": _client,
        "api": _api,
        "warnings": _warnings,
        "signin": _signin,
        "retry": _retry,
        "smtp": _smtp,
    }
    while step != "done":
        step = handlers[step](session)
    return session.account


def _card(ui: Ui, title: str, lines: list[str]) -> None:
    print()
    print(ui.heading(title))
    print(ui.dim("-" * min(ui.width, 60)))
    for line in lines:
        print(f"  {line}")


def _options(rows: list[tuple[str, str, str]]) -> list[prompts.Option]:
    return [prompts.Option(label, value, detail) for label, value, detail in rows]


def _choose(
    ui: Ui,
    title: str,
    rows: list[tuple[str, str, str]],
    *,
    back: bool = True,
) -> str | None:
    chosen = prompts.choose(title, _options(rows), ui=ui, back=back)
    return None if chosen is None else str(chosen)


def _route(session: _Session) -> str:
    _card(
        session.ui,
        "Gmail OAuth route",
        [
            "API route: HTTPS lanes plus one SMTP seat. Recommended for batches.",
            "One app-password SMTP seat sends about 5 messages in 2-6 minutes",
            "at default pacing, and Gmail may throttle the mailbox.",
        ],
    )
    choice = _choose(
        session.ui,
        "OAuth route",
        [
            ("Use the Gmail API route", "continue", "recommended for batches"),
            ("Cancel", "cancel", "nothing changes"),
        ],
        back=False,
    )
    if choice in (None, "cancel"):
        raise CANCELLED
    provider = get(session.client, f"/api/providers/{session.account['provider']}")
    return "api" if provider["ready"] else "client"


def _client(session: _Session) -> str:
    _card(
        session.ui,
        "OAuth client",
        [
            "Import the Desktop client JSON from Google Cloud.",
            "APIs and Services -> Credentials -> OAuth client -> Download JSON.",
            "The daemon stores it encrypted.",
        ],
    )
    choice = _choose(
        session.ui,
        "OAuth client",
        [
            ("Import the client JSON", "import", "read it from disk"),
            ("Back", "back", "return to the route card"),
            ("Cancel", "cancel", "nothing changes"),
        ],
    )
    if choice == "back":
        return "route"
    if choice in (None, "cancel"):
        raise CANCELLED
    while True:
        path = prompts.ask(
            "Client JSON path, blank to go back",
            ui=session.ui,
            required=False,
            field="--client",
        )
        if not path.strip():
            return "route"
        try:
            oauth_setup.import_client(
                session.ui,
                session.account["provider"],
                client=session.client,
                path=path.strip(),
            )
        except CliError as error:
            print(session.ui.result(False, error.label))
            if error.hint:
                print(f"  {error.hint}")
            continue
        return "api"


def _api(session: _Session) -> str:
    project = oauth_setup.project_id(session.client, session.account["provider"])
    oauth_setup.print_enable(session.ui, project)
    rows = [("I enabled the Gmail API", "continue", "run the sign-in next")]
    if oauth_setup.gcloud_path() and project:
        rows.insert(
            0,
            ("Run gcloud services enable", "gcloud", "uses the local gcloud"),
        )
    rows.extend(
        [
            ("Show the link again", "show", "print the project link"),
            ("Back", "back", "return to the route card"),
            ("Cancel", "cancel", "nothing changes"),
        ]
    )
    choice = _choose(session.ui, "Gmail API", rows)
    if choice == "back":
        return "route"
    if choice in (None, "cancel"):
        raise CANCELLED
    if choice == "show":
        return "api"
    if choice == "gcloud":
        if oauth_setup.enable_with_gcloud(project):
            return "warnings"
        return "api"
    return "warnings"


def _warnings(session: _Session) -> str:
    oauth_setup.warnings(session.ui)
    choice = _choose(
        session.ui,
        "Before sign-in",
        [
            ("Continue to Google sign-in", "continue", "opens the consent page"),
            ("Back", "back", "return to the Gmail API card"),
            ("Cancel", "cancel", "nothing changes"),
        ],
    )
    if choice == "back":
        return "api"
    if choice in (None, "cancel"):
        raise CANCELLED
    return "signin"


def _signin(session: _Session) -> str:
    if session.attempt is None:
        session.attempt = post(
            session.client,
            f"/api/accounts/{session.account['id']}/attempts",
        )
        print()
        print(f"Open this URL:\n  {session.attempt['authorization_url']}")
        print(f"It expires at {session.attempt['expires_at']}")
        webbrowser.open(session.attempt["authorization_url"])
    choice = _choose(
        session.ui,
        "Google sign-in",
        [
            ("Wait for the browser sign-in", "wait", "poll until it finishes"),
            ("Paste the redirect URL", "paste", "manual or remote browser"),
            ("Back", "back", "cancel this attempt and change a setting"),
            ("Cancel", "cancel", "nothing is connected"),
        ],
    )
    if choice == "back":
        _cancel_attempt(session)
        return "warnings"
    if choice in (None, "cancel"):
        _cancel_attempt(session)
        raise CANCELLED
    if choice == "paste":
        url = prompts.ask(
            "Paste the full redirect URL",
            ui=session.ui,
            field="redirect URL",
        )
        oauth_setup.deliver_redirect(url.strip())
    return _wait(session)


def _wait(session: _Session) -> str:
    try:
        result = wait(
            session.client,
            session.account["id"],
            session.timeout,
            session.attempt.get("id") if session.attempt else None,
        )
    except CliError as error:
        if _api_disabled(error):
            session.attempt = None
            return "retry"
        raise CliError(error.label, code=error.code, hint=error.hint) from error
    if result["status"] != "connected":
        raise CliError(
            "the browser sign-in did not finish",
            code="oauth_incomplete",
            hint="run downcroc account connect again",
        )
    session.account = result
    return "smtp"


def _api_disabled(error: CliError) -> bool:
    if "gmail api is disabled" in error.message.lower():
        return True
    return bool(error.fields.get("project_id"))


def _retry(session: _Session) -> str:
    _card(
        session.ui,
        "Gmail API check",
        [
            "The token was kept, so the browser consent does not have to repeat.",
            "Enable the Gmail API in the same project, then retry the check.",
            "A 403 accessNotConfigured here usually means the API is still off.",
        ],
    )
    project = oauth_setup.project_id(session.client, session.account["provider"])
    print(f"  {oauth_setup.enable_url(project)}")
    choice = _choose(
        session.ui,
        "Gmail API check",
        [
            ("Retry the check", "retry", "reuse the stored token"),
            ("Back", "back", "open the enable link again"),
            ("Cancel", "cancel", "leave the account pending"),
        ],
    )
    if choice == "back":
        return "api"
    if choice in (None, "cancel"):
        raise CANCELLED
    try:
        post(
            session.client,
            f"/api/accounts/{session.account['id']}/verify",
            None,
            refresh="true",
        )
    except CliError as error:
        print(session.ui.result(False, error.label))
        if error.hint:
            print(f"  {error.hint}")
        return "retry"
    session.account = get(
        session.client,
        f"/api/accounts/{session.account['id']}",
    )
    return "smtp"


def _smtp(session: _Session) -> str:
    bindings = get(
        session.client,
        f"/api/accounts/{session.account['id']}/transports",
    )
    if any(item["kind"] == "smtp" for item in bindings):
        _card(
            session.ui,
            "SMTP seat",
            [
                "SMTP over OAuth is already provisioned for this mailbox.",
                "One seat sends about 5 messages in 2-6 minutes at default pacing.",
                "OAuth uses XOAUTH2, so no app password is needed.",
            ],
        )
        return "done"
    _card(
        session.ui,
        "SMTP binding",
        [
            "No SMTP binding is present on this mailbox.",
            "SMTP is the stable fallback; the API lanes carry the batch.",
            "One seat sends about 5 messages in 2-6 minutes at default pacing.",
            "OAuth uses XOAUTH2, so this binding needs no app password.",
            "The configured SMTP seat count chooses the active rotation.",
        ],
    )
    choice = _choose(
        session.ui,
        "Add the SMTP binding?",
        [
            ("Add the SMTP binding", "add", "one authenticated seat"),
            ("Skip", "skip", "keep API lanes only"),
        ],
        back=False,
    )
    if choice != "add":
        return "done"
    try:
        post(
            session.client,
            f"/api/accounts/{session.account['id']}/transports",
            {"kind": "smtp"},
        )
    except CliError as error:
        print(session.ui.result(False, error.label))
        if error.hint:
            print(f"  {error.hint}")
        return "done"
    print(session.ui.result(True, "SMTP binding added"))
    return "done"


def _cancel_attempt(session: _Session) -> None:
    if session.attempt is None:
        return
    try:
        delete(session.client, f"/api/attempts/{session.attempt['id']}")
    except CliError:
        pass
    session.attempt = None
