from __future__ import annotations

import argparse

from downcroc.cli.parser.common import common, duration, policy_flags
from downcroc.cli.parser.provider import IMAP_TLS, SMTP_TLS


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
        choices=[
            "start",
            "stop",
            "restart",
            "status",
            "install",
            "uninstall",
            "pause",
            "resume",
        ],
        help="what to do; asked when omitted",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the service definition without installing it",
    )
    parser.add_argument(
        "--for",
        dest="for_s",
        type=duration,
        help="pause duration such as 30s, 15m, 2h, or 7d",
    )
    parser.add_argument("--reason", help="why sending is paused")
    common(parser)


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
    listing.add_argument(
        "--archived",
        action="store_true",
        help="list archived accounts instead",
    )
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
    remove.add_argument(
        "--reassign-to", metavar="ID", help="move queued jobs to this account"
    )
    remove.add_argument("--force-jobs", action="store_true", help="delete unsent jobs")
    remove.add_argument(
        "--force-history",
        action="store_true",
        help="delete sent history as well",
    )
    remove.add_argument(
        "--dry-run", action="store_true", help="show what would be deleted"
    )
    common(remove, yes=True)

    deletion = actions.add_parser(
        "deletion", help="preview what deleting an account removes"
    )
    deletion.add_argument("account_id", nargs="?")
    common(deletion)

    archive = actions.add_parser(
        "archive", help="archive an account and stop its watcher"
    )
    archive.add_argument("account_id", nargs="?")
    common(archive, yes=True)

    unarchive = actions.add_parser("unarchive", help="restore an archived account")
    unarchive.add_argument("account_id", nargs="?")
    common(unarchive, yes=True)

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
        "--client",
        metavar="ID",
        help="use this imported oauth client",
    )
    attempt.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="seconds to wait with --wait (default 180)",
    )
    attempt.add_argument(
        "--redirect-url",
        metavar="URL",
        help="headless: full loopback callback URL to deliver",
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
    connect.add_argument(
        "--client",
        metavar="ID",
        help="use this imported oauth client",
    )
    connect.add_argument(
        "--transport",
        choices=("smtp", "gmail_api"),
        help="binding to create after an oauth connect",
    )
    connect.add_argument(
        "--redirect-url",
        metavar="URL",
        help="headless: full loopback callback URL to deliver",
    )
    common(connect)

    verify = actions.add_parser("verify", help="verify an account login")
    verify.add_argument("account_id", nargs="?")
    verify.add_argument("--refresh", action="store_true", help="re-check the login now")
    common(verify)

    sync = actions.add_parser("sync", help="request an INBOX sync")
    sync.add_argument("account_id", nargs="?")
    common(sync)

    inbound = actions.add_parser(
        "inbound",
        help="choose the inbound owner for one mailbox",
        epilog=(
            "examples:\n"
            "  downcroc account inbound acct_... --source gmail_api\n"
            "  downcroc account inbound acct_... --source auto"
        ),
    )
    inbound.add_argument("account_id", nargs="?")
    inbound.add_argument(
        "--source",
        required=True,
        choices=("auto", "imap", "gmail_api"),
        help="auto keeps IMAP and sweeps with the Gmail API",
    )
    common(inbound)

    pause = actions.add_parser("pause", help="pause sending for one or more accounts")
    pause.add_argument("account_id", nargs="+")
    pause.add_argument("--reason", help="why sending is paused")
    common(pause)

    resume = actions.add_parser(
        "resume", help="resume sending for one or more accounts"
    )
    resume.add_argument("account_id", nargs="+")
    resume.add_argument("--reason", help="why sending is resumed")
    common(resume)

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

    transport = actions.add_parser(
        "transport",
        help="inspect and tune the send transports of a mailbox",
        epilog=(
            "examples:\n"
            "  downcroc account transport list acct_...\n"
            "  downcroc account transport add acct_... --kind gmail_api\n"
            "  downcroc account transport test acct_... trn_..."
        ),
    )
    transport_actions = transport.add_subparsers(
        dest="transport_action", required=False
    )

    transport_list = transport_actions.add_parser("list", help="list send transports")
    transport_list.add_argument("account_id", nargs="?")
    common(transport_list)

    transport_add = transport_actions.add_parser("add", help="add a send transport")
    transport_add.add_argument("account_id", nargs="?")
    transport_add.add_argument(
        "--kind",
        choices=["smtp", "gmail_api"],
        help="how the mailbox sends; asked when omitted",
    )
    transport_add.add_argument(
        "--priority", type=int, default=0, help="higher is tried first"
    )
    transport_add.add_argument(
        "--max-concurrency", type=int, help="parallel sends over the Gmail API"
    )
    transport_add.add_argument(
        "--rate-per-min", type=int, help="cap API calls per minute"
    )
    transport_add.add_argument(
        "--oauth-client", metavar="ID", help="OAuth client used for the API"
    )
    common(transport_add)

    transport_set = transport_actions.add_parser("set", help="change a send transport")
    transport_set.add_argument("account_id", nargs="?")
    transport_set.add_argument("binding_id", nargs="?")
    transport_set.add_argument("--priority", type=int, help="higher is tried first")
    transport_set.add_argument(
        "--max-concurrency", type=int, help="parallel sends over the Gmail API"
    )
    transport_set.add_argument(
        "--rate-per-min", type=int, help="cap API calls per minute"
    )
    state = transport_set.add_mutually_exclusive_group()
    state.add_argument(
        "--on", action="store_true", dest="enabled", help="enable the transport"
    )
    state.add_argument(
        "--off", action="store_false", dest="enabled", help="disable the transport"
    )
    transport_set.set_defaults(enabled=None)
    common(transport_set)

    transport_remove = transport_actions.add_parser(
        "remove", help="remove a send transport"
    )
    transport_remove.add_argument("account_id", nargs="?")
    transport_remove.add_argument("binding_id", nargs="?")
    common(transport_remove, yes=True)

    transport_test = transport_actions.add_parser(
        "test", help="probe a send transport now"
    )
    transport_test.add_argument("account_id", nargs="?")
    transport_test.add_argument("binding_id", nargs="?")
    common(transport_test)

    policy = actions.add_parser(
        "policy",
        help="show or override the send policy of a mailbox",
        epilog=(
            "examples:\n"
            "  downcroc account policy show acct_...\n"
            "  downcroc account policy set acct_... --daily-allowance 50\n"
            "  downcroc account policy set acct_... --off --for 2h\n"
            "  downcroc account policy clear acct_..."
        ),
    )
    policy_actions = policy.add_subparsers(dest="policy_action", required=False)

    policy_show = policy_actions.add_parser("show", help="show the effective policy")
    policy_show.add_argument("account_id", nargs="?")
    common(policy_show)

    policy_set = policy_actions.add_parser("set", help="set a policy override")
    policy_set.add_argument("account_id", nargs="?")
    policy_flags(policy_set)
    common(policy_set)

    policy_clear = policy_actions.add_parser("clear", help="remove the override")
    policy_clear.add_argument("account_id", nargs="?")
    common(policy_clear)

    policy_clear_temp = policy_actions.add_parser(
        "clear-temporary", help="remove the temporary override only"
    )
    policy_clear_temp.add_argument("account_id", nargs="?")
    common(policy_clear_temp)


def attach_auth(commands: argparse._SubParsersAction) -> None:
    auth = commands.add_parser(
        "auth",
        help="inspect daemon authentication",
        epilog="example:\n  downcroc auth status --json",
    )
    actions = auth.add_subparsers(dest="action", required=True)
    status = actions.add_parser("status", help="check the daemon token")
    common(status)
