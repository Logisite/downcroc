from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import require


def register_state(broker: Broker) -> None:
    broker.register(("kv.get",), kv_get)
    broker.register(("kv.set",), kv_set)
    broker.register(("kv.delete",), kv_delete)
    broker.register(("kv.list",), kv_list)
    broker.register(("log",), log)


def kv_get(inv: Invocation, params: dict[str, Any]) -> Any:
    return inv.store.kv_get(inv.extension, require(inv, "key"))


def kv_set(inv: Invocation, params: dict[str, Any]) -> Any:
    value = params.get("value")
    text = value if isinstance(value, str) else str(value)
    inv.store.kv_set(inv.extension, require(inv, "key"), text)
    return {"ok": True}


def kv_delete(inv: Invocation, params: dict[str, Any]) -> Any:
    inv.store.kv_delete(inv.extension, require(inv, "key"))
    return {"ok": True}


def kv_list(inv: Invocation, params: dict[str, Any]) -> Any:
    return inv.store.kv_list(inv.extension)


def log(inv: Invocation, params: dict[str, Any]) -> Any:
    level = str(params.get("level", "info"))
    writer = getattr(inv.log, level, inv.log.info)
    writer(
        f"extension.message.{level}",
        extension=inv.extension,
        text=str(params.get("message", params.get("text", ""))),
        fields=dump_fields(params.get("fields")),
    )
    return {"ok": True}


def dump_fields(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
