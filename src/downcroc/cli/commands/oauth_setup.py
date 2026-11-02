from __future__ import annotations

import shutil
import subprocess
import urllib.request

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui

ENABLE_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com"


def import_client(ui: Ui, provider_id: str = "gmail") -> None:
    if not ui.interactive:
        raise CliError(
            "the gmail oauth client is not configured",
            code="oauth_not_configured",
            hint="run downcroc provider credentials set gmail --client PATH",
        )
    print()
    print("Import the Desktop OAuth client JSON from Google Cloud")
    print("  APIs and Services -> Credentials -> OAuth client -> Download JSON")
    path = prompts.ask("Client JSON path", ui=ui, field="--client")
    payload = path_tools.read_text(path, field="--client")
    paths, _, _ = load()
    with api(paths) as client:
        post(
            client,
            "/api/oauth-clients",
            {"provider_id": provider_id, "payload": payload, "label": ""},
        )


def project_id(client, provider_id: str = "gmail") -> str | None:
    found = get(client, "/api/oauth-clients", provider_id=provider_id)
    return found[0].get("project_id") if found else None


def enable_gmail_api(ui: Ui, project: str | None) -> None:
    link = ENABLE_URL + (f"?project={project}" if project else "")
    print()
    print("Enable the Gmail API before authorizing")
    print(f"  {link}")
    print("  Without this the first API call fails with 403 accessNotConfigured.")
    gcloud = shutil.which("gcloud")
    if (
        gcloud
        and project
        and ui.interactive
        and prompts.confirm(
            "Run gcloud services enable gmail.googleapis.com now?",
            ui=ui,
            default=False,
        )
    ):
        result = subprocess.run(
            [
                gcloud,
                "services",
                "enable",
                "gmail.googleapis.com",
                "--project",
                project,
            ],
            check=False,
        )
        if result.returncode != 0:
            print("gcloud returned an error; use the link above instead")


def warnings(ui: Ui) -> None:
    print()
    print("Google will show an unverified-app screen.")
    print("  Choose Advanced, then continue to the app you configured.")
    print("  In Testing mode, refresh tokens expire after 7 days.")
    print("  Publish the app or use a Workspace internal app for long-lived access.")


def deliver_redirect(url: str) -> None:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=30) as response:
            response.read()
    except OSError as error:
        raise CliError(
            "the redirect URL could not be delivered",
            code="oauth_callback_failed",
            hint="paste the complete loopback callback URL",
        ) from error
