from __future__ import annotations

from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import action, need_daemon, rows
from downcroc.cli.ui.menu import Item, quit_menu, run, run_args
from downcroc.cli.ui.session import Ui


def _account_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/accounts")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [
            Item(
                "No accounts yet",
                detail="add one first",
                action=action(ui, "account", "add"),
            )
        ]
    return [
        Item(
            row["address"],
            detail=f"{row['status']}  {row['id']}",
            action=action(ui, "account", verb, row["id"]),
        )
        for row in found
    ]


def _delete_account(ui: Ui, row: dict) -> None:
    if prompts.confirm(f"Delete {row['address']}?", ui=ui):
        run_args(ui, "account", "delete", row["id"], "--yes")


def _delete_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/accounts")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No accounts yet", detail="nothing to delete")]
    return [
        Item(
            row["address"],
            detail=f"{row['status']}  {row['id']}",
            action=lambda row=row: _delete_account(ui, row),
        )
        for row in found
    ]


def _watch_items(ui: Ui, enabled: bool) -> list[Item]:
    found = rows(ui, "/api/accounts")
    if found is None:
        return need_daemon(ui)
    flag = "--on" if enabled else "--off"
    return [
        Item(
            row["address"],
            detail=row["status"],
            action=action(ui, "account", "watch", row["id"], flag),
        )
        for row in found
    ]


def accounts_menu(ui: Ui) -> None:
    run(
        ui,
        "Accounts",
        [
            Item(
                "List accounts",
                detail="state and last activity",
                action=action(ui, "account", "list"),
            ),
            Item(
                "Add an account",
                detail="provider and address",
                action=action(ui, "account", "add"),
            ),
            Item(
                "Connect an account",
                detail="check the login",
                children=_account_items(ui, "connect"),
            ),
            Item(
                "Show an account",
                detail="full record",
                children=_account_items(ui, "show"),
            ),
            Item(
                "Verify a login",
                detail="re-check without sending",
                children=_account_items(ui, "verify"),
            ),
            Item(
                "Sync the inbox",
                detail="request a fetch now",
                children=_account_items(ui, "sync"),
            ),
            Item(
                "Turn the watcher on",
                detail="watch for replies",
                children=_watch_items(ui, True),
            ),
            Item(
                "Turn the watcher off",
                detail="stop watching",
                children=_watch_items(ui, False),
            ),
            Item(
                "Delete an account",
                detail="asks before removing",
                children=_delete_items(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def _provider_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/providers")
    if found is None:
        return need_daemon(ui)
    return [
        Item(
            row["label"],
            detail=f"{row['id']}  {'ready' if row['ready'] else 'needs setup'}",
            action=action(ui, "provider", verb, row["id"]),
        )
        for row in found
    ]


def _remove_provider(ui: Ui, row: dict) -> None:
    if prompts.confirm(f"Remove the {row['id']} provider?", ui=ui):
        run_args(ui, "provider", "remove", row["id"], "--yes")


def _remove_providers(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/providers")
    if found is None:
        return need_daemon(ui)
    return [
        Item(
            row["label"],
            detail=row["id"],
            action=lambda row=row: _remove_provider(ui, row),
        )
        for row in found
    ]


def providers_menu(ui: Ui) -> None:
    run(
        ui,
        "Providers",
        [
            Item(
                "List providers",
                detail="readiness and hosts",
                action=action(ui, "provider", "list"),
            ),
            Item(
                "Show a provider",
                detail="hosts, ports, and TLS",
                children=_provider_items(ui, "show"),
            ),
            Item(
                "Add a provider",
                detail="name the hosts",
                action=action(ui, "provider", "add"),
            ),
            Item(
                "Edit a provider",
                detail="change the declaration",
                children=_provider_items(ui, "edit"),
            ),
            Item(
                "Remove a provider",
                detail="asks before removing",
                children=_remove_providers(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def service_menu(ui: Ui) -> None:
    run(
        ui,
        "Service",
        [
            Item(
                "Status",
                detail="pid, port, and uptime",
                action=action(ui, "service", "status"),
            ),
            Item("Start", detail="start the daemon", action=action(ui, "service", "start")),
            Item("Stop", detail="stop the daemon", action=action(ui, "service", "stop")),
            Item(
                "Restart",
                detail="stop, then start",
                action=action(ui, "service", "restart"),
            ),
            Item(
                "Install",
                detail="start with the session",
                action=action(ui, "service", "install"),
            ),
            Item(
                "Uninstall",
                detail="remove the unit",
                action=action(ui, "service", "uninstall"),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def vault_menu(ui: Ui) -> None:
    run(
        ui,
        "Vault",
        [
            Item(
                "Status",
                detail="locked or unlocked",
                action=action(ui, "vault", "status"),
            ),
            Item(
                "Create",
                detail="set a master password",
                action=action(ui, "vault", "init"),
            ),
            Item(
                "Unlock",
                detail="type the master password",
                action=action(ui, "vault", "unlock"),
            ),
            Item(
                "Lock",
                detail="seal the vault now",
                action=action(ui, "vault", "lock"),
            ),
            Item(
                "Keyring status",
                detail="the system credential store",
                action=action(ui, "vault", "keyring", "status"),
            ),
            Item(
                "Enable the keyring",
                detail="remember the master password",
                action=action(ui, "vault", "keyring", "enable"),
            ),
            Item(
                "Disable the keyring",
                detail="forget the master password",
                action=action(ui, "vault", "keyring", "disable"),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def home_menu(ui: Ui) -> None:
    from downcroc.cli.ui.menus_settings import settings_menu
    from downcroc.cli.ui.menus_work import backup_menu

    run(
        ui,
        "downcroc",
        [
            Item(
                "Send a campaign",
                detail="file, CSV, or compose",
                action=action(ui, "send"),
            ),
            Item(
                "Review pending batches",
                detail="approve or cancel",
                action=action(ui, "review"),
            ),
            Item(
                "Status",
                detail="daemon, vault, accounts, queue",
                action=action(ui, "status"),
            ),
            Item(
                "Accounts",
                detail="add, connect, verify",
                action=lambda: accounts_menu(ui),
            ),
            Item(
                "Mail",
                detail="inbox, threads, replies",
                action=action(ui, "mail", "list"),
            ),
            Item(
                "Failures",
                detail="inspect and retry",
                action=action(ui, "failed", "list"),
            ),
            Item(
                "Settings",
                detail="edit the configuration",
                action=lambda: settings_menu(ui),
            ),
            Item(
                "Back up or restore",
                detail="bundles and restores",
                action=lambda: backup_menu(ui),
            ),
            Item(
                "Help",
                detail="topics and commands",
                action=action(ui, "help"),
            ),
            Item("Quit", action=quit_menu),
        ],
    )
