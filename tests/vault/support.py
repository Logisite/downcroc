from __future__ import annotations

from tests.conftest import Stack
from tests.harness.logs import events


def lock(stack: Stack) -> None:
    stack.api.post("/api/vault/lock")


def unlock(stack: Stack) -> None:
    stack.api.unlock()


def vault_path(stack: Stack) -> str:
    return str(stack.daemon.data_home / "downcroc" / "vault.enc")


def pruned_events(stack: Stack) -> list[dict]:
    return events(stack).get("vault.secrets_pruned", [])
