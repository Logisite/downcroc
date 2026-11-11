from __future__ import annotations

import sqlite3
from contextlib import closing

from tests.conftest import Stack
from tests.harness.logs import events


def database(stack: Stack) -> str:
    return str(stack.daemon.data_home / "downcroc" / "downcroc.db")


def lock(stack: Stack) -> None:
    stack.api.post("/api/vault/lock")


def unlock(stack: Stack) -> None:
    stack.api.unlock()


def vault_path(stack: Stack) -> str:
    return str(stack.daemon.data_home / "downcroc" / "vault.enc")


def pruned_events(stack: Stack) -> list[dict]:
    return events(stack).get("vault.secrets_pruned", [])


def set_credential_key(stack: Stack, account_id: str, key: str) -> None:
    with closing(sqlite3.connect(database(stack), timeout=10)) as connection:
        connection.execute(
            "update accounts set credential_key = ? where id = ?",
            (key, account_id),
        )
        connection.commit()


def set_status(stack: Stack, account_id: str, status: str) -> None:
    with closing(sqlite3.connect(database(stack), timeout=10)) as connection:
        connection.execute(
            "update accounts set status = ? where id = ?",
            (status, account_id),
        )
        connection.commit()
