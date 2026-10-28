from __future__ import annotations

import argparse

from downcroc.cli.parser.common import common

IMAP_TLS = ["ssl", "starttls", "none"]
SMTP_TLS = ["starttls", "ssl", "none"]
AUTH_KINDS = ["oauth2", "app_password", "none"]


def service(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "service",
        help="control the running daemon",
        epilog=(
            "examples:\n"
            "  downcroc service start\n"
            "  downcroc service status\n"
            "  downcroc service restart"
        ),
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["start", "stop", "restart", "status", "install", "uninstall"],
        help="what to do; asked when omitted",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the service definition without installing it",
    )
    common(parser)


def vault(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "vault",
        help="create, inspect, and unlock the credential vault",
        epilog=(
            "examples:\n"
            "  downcroc vault init\n"
            "  downcroc vault unlock --password-file /run/secrets/downcroc\n"
            "  downcroc vault keyring status"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    status = actions.add_parser("status", help="show the vault state")
    common(status)

    init = actions.add_parser("init", help="create the vault")
    _password_options(init)
    common(init)

    unlock = actions.add_parser("unlock", help="unlock the vault")
    _password_options(unlock)
    common(unlock)

    lock = actions.add_parser("lock", help="lock the vault")
    lock.add_argument(
        "--forget",
        action="store_true",
        help="also delete the stored master password",
    )
    common(lock)

    keyring = actions.add_parser("keyring", help="control the credential store")
    keyring.add_argument(
        "action",
        choices=["status", "enable", "disable"],
        help="show, turn on, or turn off the store",
    )
    _password_options(keyring)
    common(keyring)


def _password_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin",
    )
    parser.add_argument(
        "--password-file",
        metavar="PATH",
        help="read the password from a 0600 file",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--keyring",
        action="store_true",
        help="use the system credential store",
    )
    group.add_argument(
        "--no-keyring",
        action="store_true",
        help="do not read or write the credential store",
    )


def provider(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "provider",
        help="inspect and add provider declarations",
        epilog=(
            "examples:\n"
            "  downcroc provider list\n"
            "  downcroc provider show gmail\n"
            "  downcroc provider add fastmail"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list providers and readiness")
    common(listing)

    show = actions.add_parser("show", help="show one provider")
    show.add_argument("provider_id", nargs="?")
    common(show)

    add = actions.add_parser("add", help="write a provider declaration")
    add.add_argument("provider_id", nargs="?")
    _declaration(add)
    common(add)

    edit = actions.add_parser("edit", help="change a provider declaration")
    edit.add_argument("provider_id", nargs="?")
    _declaration(edit)
    common(edit)

    remove = actions.add_parser("remove", help="remove a provider declaration")
    remove.add_argument("provider_id", nargs="?")
    common(remove, yes=True)


def _declaration(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", help="name shown in lists")
    parser.add_argument("--imap-host", help="IMAP server host")
    parser.add_argument("--imap-port", type=int, help="IMAP port, usually 993")
    parser.add_argument("--imap-tls", choices=IMAP_TLS, help="IMAP encryption")
    parser.add_argument("--smtp-host", help="SMTP server host")
    parser.add_argument("--smtp-port", type=int, help="SMTP port, usually 587")
    parser.add_argument("--smtp-tls", choices=SMTP_TLS, help="SMTP encryption")
    parser.add_argument(
        "--auth-kind",
        choices=AUTH_KINDS,
        help="app password, oauth client, or none",
    )
    parser.add_argument("--sent-folder", help="folder holding sent mail")
    parser.add_argument("--notes", help="a note shown by provider list")
    parser.add_argument("--oauth-client-id", help="OAuth application client id")
    parser.add_argument("--oauth-tenant", help="OAuth tenant, for Microsoft")
    parser.add_argument(
        "--password-file",
        metavar="PATH",
        help="read the OAuth client secret from a 0600 file",
    )


def account(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "account",
        help="manage mail accounts",
        epilog=(
            "examples:\n"
            "  downcroc account add --provider gmail --address you@example.com\n"
            "  downcroc account connect acct_...\n"
            "  downcroc account list"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list accounts")
    common(listing)

    show = actions.add_parser("show", help="show one account")
    show.add_argument("account_id", nargs="?")
    common(show)

    add = actions.add_parser("add", help="create a pending account")
    add.add_argument("--provider", help="provider id; asked when omitted")
    add.add_argument("--address", help="mailbox address; asked when omitted")
    add.add_argument("--label", default="", help="name shown in lists")
    add.add_argument("--imap-host", help="override the IMAP host")
    add.add_argument("--imap-port", type=int, help="override the IMAP port")
    add.add_argument("--imap-tls", choices=IMAP_TLS, help="override IMAP TLS")
    add.add_argument("--smtp-host", help="override the SMTP host")
    add.add_argument("--smtp-port", type=int, help="override the SMTP port")
    add.add_argument("--smtp-tls", choices=SMTP_TLS, help="override SMTP TLS")
    add.add_argument("--oauth-client-id", help="OAuth application client id")
    add.add_argument("--oauth-tenant", help="OAuth tenant, for Microsoft")
    add.add_argument("--password-file", metavar="PATH", help="OAuth secret file")
    common(add)

    remove = actions.add_parser("delete", help="delete an account")
    remove.add_argument("account_id", nargs="?")
    common(remove, yes=True)

    providers = actions.add_parser("providers", help="alias of provider list")
    common(providers)

    attempt = actions.add_parser("attempt", help="start an OAuth connect attempt")
    attempt.add_argument("account_id", nargs="?")
    attempt.add_argument(
        "--wait",
        action="store_true",
        help="wait for the account to connect",
    )
    attempt.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="seconds to wait with --wait (default 180)",
    )
    common(attempt, timeout=False)

    connect = actions.add_parser("connect", help="connect an account")
    connect.add_argument("account_id", nargs="?")
    connect.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the app password from stdin",
    )
    connect.add_argument(
        "--password-file", metavar="PATH", help="read the app password from a file"
    )
    common(connect)

    verify = actions.add_parser("verify", help="verify an account login")
    verify.add_argument("account_id", nargs="?")
    verify.add_argument("--refresh", action="store_true", help="re-check the login now")
    common(verify)

    sync = actions.add_parser("sync", help="request an INBOX sync")
    sync.add_argument("account_id", nargs="?")
    common(sync)

    watch = actions.add_parser("watch", help="enable or disable the watcher")
    watch.add_argument("account_id", nargs="?")
    state = watch.add_mutually_exclusive_group()
    state.add_argument(
        "--on", action="store_true", dest="enabled", help="start the watcher"
    )
    state.add_argument(
        "--off", action="store_false", dest="enabled", help="stop the watcher"
    )
    watch.set_defaults(enabled=None)
    common(watch)


def attach_auth(commands: argparse._SubParsersAction) -> None:
    auth = commands.add_parser(
        "auth",
        help="inspect daemon authentication",
        epilog="example:\n  downcroc auth status --json",
    )
    actions = auth.add_subparsers(dest="action", required=True)
    status = actions.add_parser("status", help="check the daemon token")
    common(status)
