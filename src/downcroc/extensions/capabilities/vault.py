from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_vault(broker: Broker) -> None:
    names = (
        "vault.lock",
        "vault.unlock",
        "vault.status",
        "secret.put",
        "secret.delete",
        "secret.list",
        "secret.exists",
        "key.rotate",
    )
    broker.register(names, vault)


def vault(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    if name == "vault.lock":
        return dump(services.vault.lock(str(inv.param("reason", "extension"))))
    if name == "vault.unlock":
        return dump(services.vault.unlock(require(inv, "password")))
    if name == "vault.status":
        return dump(services.vault.status())
    if name == "secret.delete":
        return {"ok": services.vault.delete_secret(require(inv, "key"))}
    if name == "secret.exists":
        return {"exists": require(inv, "key") in set(services.vault.keys())}
    if name == "secret.list":
        return {"keys": sorted(services.vault.keys())}
    return {"ok": True, "capability": name}
