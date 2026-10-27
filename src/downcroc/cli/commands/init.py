from __future__ import annotations

from downcroc.cli.client import api, get, post, put
from downcroc.cli.commands import accounts, service, vault
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime import keyring
from downcroc.runtime.service.lifecycle import status
from downcroc.version import __version__

GMAIL = {"gmail", "gmail-app-password"}
CHOICES = (
    ("gmail", "Gmail", "imap.gmail.com, app password or OAuth client"),
    ("microsoft", "Microsoft 365", "needs an Entra app registration"),
    ("generic", "Other IMAP", "you supply the hosts"),
)


def _paths(ui: Ui, paths: object) -> None:
    if ui.json_mode:
        return
    print(f"downcroc {__version__}")
    record(
        {
            "config": str(paths.config),
            "data": str(paths.data),
            "state": str(paths.state),
        }
    )
    print()
    print("This directory becomes the only place downcroc stores anything.")


def _service_step(args: object, ui: Ui) -> dict:
    if args.service and args.no_service:
        raise CliError(
            "choose --service or --no-service, not both",
            code="usage",
            exit_code=2,
        )
    if ui.json_mode:
        return status(load()[0])
    current = status(load()[0])
    if current.get("state") == "running":
        record({"daemon": f"already running, pid {current['pid']}, {current['url']}"})
        return current
    if args.service:
        choice = "install"
    elif args.no_service:
        choice = "now"
    else:
        choice = prompts.choose(
            "Start the daemon",
            [
                prompts.Option("Run it now", "now", "it stops when this session ends"),
                prompts.Option(
                    "Install it as a login service",
                    "install",
                    "recommended",
                ),
                prompts.Option("Do nothing", "skip", "start it yourself later"),
            ],
            ui=ui,
            back=False,
        )
        if choice is None:
            choice = "skip"
    if choice == "skip":
        record({"daemon": "not started"})
        return current
    if choice == "install":
        installed = service.install_now(args)
        if installed is None:
            record({"daemon": "not installed"})
        else:
            record({"service": f"installed ({installed['kind']}), {installed['path']}"})
    service.start_now(args)
    return status(load()[0])


def _vault_step(args: object, ui: Ui) -> None:
    paths, _, _ = load()
    with api(paths) as client:
        data = get(client, "/api/vault")
    exists = (paths.data / "vault.enc").exists()
    if data["state"] == "unlocked":
        record({"vault": "unlocked"})
        return
    if exists:
        record({"vault": "exists, locked"})
        if ui.interactive and prompts.confirm("unlock it now?", ui=ui, default=True):
            vault.run(_vault_args("unlock", args))
        return
    if not ui.interactive and not (
        getattr(args, "password_stdin", False) or getattr(args, "password_file", None)
    ):
        raise CliError(
            "the vault does not exist",
            code="vault_missing",
            hint="run downcroc vault init, or pass --password-file during init",
        )
    print()
    print("Create the vault password")
    print("  This password protects every mail credential. It cannot be recovered.")
    vault.run(_vault_args("init", args))
    if ui.interactive and keyring.available():
        use = prompts.confirm(
            "Use the system credential store so you do not retype it?",
            ui=ui,
            default=True,
        )
        if use:
            print("next: downcroc vault keyring enable")
    elif not keyring.available():
        print("keyring unavailable, type the password instead")


def _vault_args(action: str, args: object) -> object:
    return type(
        "VaultArgs",
        (),
        {
            "action": action,
            "password_stdin": getattr(args, "password_stdin", False),
            "password_file": getattr(args, "password_file", None),
            "keyring": getattr(args, "keyring", False),
            "no_keyring": getattr(args, "no_keyring", False),
            "json": False,
            "quiet": True,
            "forget": False,
            "glyphs": getattr(args, "glyphs", "auto"),
            "color": getattr(args, "color", "auto"),
            "wide": False,
            "full": False,
            "no_input": True,
            "timeout": getattr(args, "timeout", None),
        },
    )()


def _account_step(args: object, ui: Ui) -> dict | None:
    paths, _, _ = load()
    with api(paths) as client:
        existing = get(client, "/api/accounts")
        rows = get(client, "/api/providers")
    if existing:
        record({"accounts": f"{len(existing)} already configured"})
        return None
    provider_id = args.account_provider
    address = args.account_address
    if provider_id is None:
        if not ui.interactive:
            record({"account": "not added"})
            return None
        print()
        choice = prompts.choose(
            "Add the first account",
            [
                *[prompts.Option(label, key, detail) for key, label, detail in CHOICES],
                prompts.Option("Skip", None, "add one later"),
            ],
            ui=ui,
            back=False,
        )
        if choice is None:
            record({"account": "not added"})
            return None
        provider_id = choice
    if address is None:
        address = prompts.ask("Address", ui=ui, field="--account-address")
    if provider_id == "gmail":
        provider_id = _gmail_door(args, ui, rows)
        if provider_id is None:
            return None
    if provider_id == "generic":
        _custom_mailbox(args, ui)
    return _create_account(args, ui, provider_id, address)


def _gmail_door(args: object, ui: Ui, rows: list[dict]) -> str | None:
    ready = {row["id"]: row for row in rows}
    doors = []
    for key, label, cost in (
        ("gmail-app-password", "App password", "about 2 minutes, no browser"),
        ("gmail", "OAuth client", "about 10 minutes in the console, once"),
    ):
        note = "" if key in ready else "not declared"
        doors.append(prompts.Option(label, key, cost if not note else note))
    if not ui.interactive:
        raise CliError(
            "the Gmail sign-in method is required",
            code="usage",
            hint="pass --account-provider gmail-app-password or gmail",
            exit_code=2,
        )
    return prompts.choose("How should downcroc sign in?", doors, ui=ui)


def _custom_mailbox(args: object, ui: Ui) -> None:
    if not ui.interactive:
        raise CliError(
            "custom IMAP needs host flags",
            code="usage",
            hint="run downcroc account add --provider generic --address A "
            "--imap-host H --smtp-host H",
        )
    values = {
        "label": "Custom IMAP",
        "imap_host": prompts.ask("IMAP host", ui=ui),
        "imap_port": int(prompts.ask("IMAP port", ui=ui, default="993")),
        "imap_tls": prompts.choose(
            "IMAP security",
            [prompts.Option("SSL", "ssl"), prompts.Option("STARTTLS", "starttls")],
            ui=ui,
        ),
        "smtp_host": prompts.ask("SMTP host", ui=ui),
        "smtp_port": int(prompts.ask("SMTP port", ui=ui, default="587")),
        "smtp_tls": prompts.choose(
            "SMTP security",
            [prompts.Option("STARTTLS", "starttls"), prompts.Option("SSL", "ssl")],
            ui=ui,
        ),
    }
    paths, _, _ = load()
    with api(paths) as client:
        put(client, "/api/providers/generic", values)
    print(f"written  {paths.config / 'providers.toml'}  [providers.generic]  mode 0600")


def _create_account(
    args: object, ui: Ui, provider_id: str, address: str
) -> dict | None:
    paths, _, _ = load()
    with api(paths) as client:
        account = post(
            client,
            "/api/accounts",
            {"provider": provider_id, "address": address, "label": ""},
        )
    record({"account": f"{account['id']} {account['address']} {account['status']}"})
    if not ui.interactive and not (
        getattr(args, "password_stdin", False) or getattr(args, "password_file", None)
    ):
        print(f"next: downcroc account connect {account['id']}")
        return account
    try:
        account = _connect(args, ui, account)
    except CliError as error:
        print(ui.result(False, error.label))
        if error.hint:
            print(f"  hint: {error.hint}")
        print("the password was not saved")
        print(f"resume with: downcroc account connect {account['id']}")
        return account
    record({"account": f"{account['id']} {account['address']} {account['status']}"})
    return account


def _connect(args: object, ui: Ui, account: dict) -> dict:
    connect_args = type(
        "ConnectArgs",
        (),
        {
            "account_id": account["id"],
            "password_stdin": getattr(args, "password_stdin", False),
            "password_file": getattr(args, "password_file", None),
            "timeout": getattr(args, "timeout", None) or 180.0,
            "json": False,
            "no_input": not ui.interactive,
            "glyphs": getattr(args, "glyphs", "auto"),
            "color": getattr(args, "color", "auto"),
            "wide": False,
            "full": False,
            "quiet": False,
        },
    )()
    with api(load()[0]) as client:
        account = accounts.connect_now(client, account, connect_args, ui)
    return account


def _test_message(args: object, ui: Ui, account: dict) -> None:
    paths, _, _ = load()
    with api(paths) as client:
        job = post(
            client,
            "/api/jobs",
            {
                "account_id": account["id"],
                "recipient": account["address"],
                "subject": "downcroc test",
                "text": "This message proves downcroc can send through this account.",
                "batch_id": "manual",
            },
        )
    record({"test": f"queued {job['id']}, check the inbox in a moment"})


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    _paths(ui, paths)
    if ui.interactive and not prompts.confirm("Continue?", ui=ui, default=True):
        raise CliError("cancelled", code="cancelled")
    report = _service_step(args, ui)
    _vault_step(args, ui)
    account = _account_step(args, ui)
    if ui.json_mode:
        json_out(
            {
                "paths": {
                    "config": str(paths.config),
                    "data": str(paths.data),
                    "state": str(paths.state),
                },
                "daemon": report.get("state"),
                "account": account["id"] if account else None,
            }
        )
        return 0
    offer = (
        account is not None
        and ui.interactive
        and account["status"] == "connected"
        and prompts.confirm("Send a test message?", ui=ui, default=False)
    )
    if offer and account is not None:
        _test_message(args, ui, account)
    print()
    record(
        {
            "done": (
                f"{1 if account else 0} account connected, "
                f"daemon {report.get('state', 'stopped')}"
            )
        }
    )
    print("next        downcroc status")
    return 0
