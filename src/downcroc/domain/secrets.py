from __future__ import annotations

KINDS = frozenset({"refresh_token", "access_token", "app_password", "client_secret"})


def secret_key(account_id: str, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown secret kind {kind}")
    return f"{account_id}:{kind}"


def client_secret_key(client_id: str) -> str:
    return f"client:{client_id}:json"
