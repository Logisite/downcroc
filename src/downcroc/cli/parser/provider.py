from __future__ import annotations

import argparse

from downcroc.cli.parser.common import common

IMAP_TLS = ["ssl", "starttls", "none"]
SMTP_TLS = ["starttls", "ssl", "none"]
AUTH_KINDS = ["oauth2", "app_password", "none"]


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

    credentials = actions.add_parser(
        "credentials", help="import and inspect oauth client credentials"
    )
    credential_actions = credentials.add_subparsers(dest="credential_action")
    credential_set = credential_actions.add_parser(
        "set", help="import a Google OAuth client JSON"
    )
    credential_set.add_argument("provider_id", nargs="?")
    credential_set.add_argument(
        "--client", metavar="PATH", help="path to the client JSON"
    )
    credential_set.add_argument("--label", help="a name for this client")
    common(credential_set)
    credential_list = credential_actions.add_parser(
        "list", help="list imported clients"
    )
    credential_list.add_argument("provider_id", nargs="?")
    common(credential_list)
    credential_show = credential_actions.add_parser("show", help="show one client")
    credential_show.add_argument("client_id", nargs="?")
    common(credential_show)
    credential_remove = credential_actions.add_parser("remove", help="delete a client")
    credential_remove.add_argument("client_id", nargs="?")
    credential_remove.add_argument(
        "--force", action="store_true", help="move dependent bindings to reauth"
    )
    common(credential_remove, yes=True)


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
        "--transport",
        choices=("smtp", "gmail_api"),
        help="send mechanism the provider supports",
    )
    parser.add_argument("--api-base-url", help="REST API base URL")
    parser.add_argument(
        "--api-max-concurrency", type=int, help="concurrent REST requests"
    )
    parser.add_argument("--api-rate-per-min", type=int, help="REST requests per minute")
    parser.add_argument(
        "--password-file",
        metavar="PATH",
        help="read the OAuth client secret from a 0600 file",
    )
