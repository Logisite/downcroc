from __future__ import annotations

from downcroc.cli.client import get, post
from downcroc.cli.errors import CliError
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def capacity_step(client, preview: dict, ui: Ui, account: str | None = None) -> dict:
    capacity = preview.get("capacity") or {}
    if not capacity.get("serial") or preview.get("total", 0) <= 1:
        return preview
    while True:
        choice = prompts.choose(
            "Capacity",
            [
                prompts.Option("Send anyway", "send", "one seat, slower"),
                prompts.Option("Add a Gmail API binding", "binding", "more lanes"),
                prompts.Option("Open accounts", "accounts", "add or connect a mailbox"),
                prompts.Option("Cancel", "cancel", "nothing is submitted"),
            ],
            ui=ui,
            back=False,
        )
        if choice is None or choice == "cancel":
            raise CliError("cancelled", code="cancelled")
        if choice == "send":
            return preview
        if choice == "accounts":
            from downcroc.cli.ui.menu import run_args

            run_args(ui, "account")
        if choice == "binding":
            accounts = get(client, "/api/accounts")
            connected = [item for item in accounts if item["status"] == "connected"]
            if not connected:
                print(ui.paint("no connected account can take a binding", "warn"))
                continue
            picked = prompts.choose(
                "Mailbox for the Gmail API binding",
                [
                    prompts.Option(
                        item["address"],
                        item["id"],
                        item["id"],
                    )
                    for item in connected
                ],
                ui=ui,
                back=False,
            )
            if picked is None:
                continue
            provider = get(client, "/api/providers/gmail")
            if not provider["ready"]:
                from downcroc.cli.commands import oauth_setup

                oauth_setup.import_client(ui)
            try:
                post(
                    client,
                    f"/api/accounts/{picked}/transports",
                    {"kind": "gmail_api"},
                )
            except CliError as error:
                print(ui.result(False, error.label))
                if error.hint:
                    print(f"  {error.hint}")
        path = preview.get("source_ref")
        if path:
            preview = post(
                client,
                "/api/batches/preview",
                {
                    "path": str(path),
                    "template": preview.get("template"),
                    "account": account,
                },
            )
