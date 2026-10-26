from __future__ import annotations

import getpass
import sys

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table


def _password(stdin: bool) -> str:
    if stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Vault password: ")
    if not password:
        raise SystemExit("a password is required")
    return password


def _show(data: dict) -> None:
    record(
        {
            "state": data["state"],
            "path": data["path"],
            "unlocked_at": data["unlocked_at"],
            "attempts_left": data["attempts_left"],
            "retry_after_s": data["retry_after_s"],
        }
    )
    accounts = data.get("accounts") or []
    if accounts:
        table(
            ["account", "credential"],
            [[item["id"], item["credential_present"]] for item in accounts],
        )


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "status":
            data = get(client, "/api/vault")
        elif args.action == "unlock":
            data = post(
                client,
                "/api/vault/unlock",
                {"password": _password(args.password_stdin)},
            )
        else:
            data = post(client, "/api/vault/lock")
    if args.json:
        json_out(data)
    else:
        _show(data)
    return 0
