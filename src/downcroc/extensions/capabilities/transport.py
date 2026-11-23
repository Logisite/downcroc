from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_transport(broker: Broker) -> None:
    names = (
        "transport.add",
        "transport.update",
        "transport.remove",
        "transport.enable",
        "transport.disable",
        "transport.test",
        "transport.set_priority",
        "transport.clear_cooldown",
        "transport.forget_health",
        "provider.install_declaration",
        "provider.set_override",
    )
    broker.register(names, transport)


def transport(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    account = require(inv, "account")
    if name == "transport.remove":
        return dump(services.transports.remove(account, require(inv, "transport")))
    if name == "transport.test":
        return dump(services.transports.test(account, require(inv, "transport")))
    if name in {"transport.clear_cooldown", "transport.forget_health"}:
        return {"ok": True, "transport": require(inv, "transport")}
    if name == "provider.set_override":
        return dump(
            services.providers.save(
                require(inv, "provider"), params.get("values") or {}
            )
        )
    if name == "provider.install_declaration":
        return {"ok": True, "provider": require(inv, "provider")}
    binding_id = require(inv, "transport")
    values: dict[str, Any] = {}
    if name == "transport.enable":
        values = {"enabled": True}
    elif name == "transport.disable":
        values = {"enabled": False}
    elif name == "transport.set_priority":
        values = {"priority": int(inv.param("priority", 0))}
    else:
        values = dict(params.get("values") or {})
    if not values:
        return {"ok": True, "transport": binding_id}
    binding = services.transports.get(account, binding_id)
    updated = services.transports.update(
        account,
        binding_id,
        enabled=bool(values.get("enabled", binding.enabled)),
        priority=int(values.get("priority", binding.priority)),
    )
    return dump(updated)
