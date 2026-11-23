from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_system(broker: Broker) -> None:
    names = (
        "service.pause",
        "service.resume",
        "service.status",
        "daemon.restart",
        "daemon.stop",
        "config.set",
        "update.check",
        "update.install",
        "notify",
        "timer.schedule",
        "timer.cancel",
        "command.register",
        "cli.run",
        "event.publish",
        "backfill.start",
        "backfill.stop",
        "backfill.scan",
        "backfill.resolve",
        "stats.rebuild",
        "stats.prune",
        "db.vacuum",
        "db.integrity_check",
        "backup.create",
        "backup.list",
        "backup.restore",
        "export.json",
        "import.json",
    )
    broker.register(names, system)


def system(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    if name == "service.pause":
        return dump(services.holds.pause_service(inv.param("reason")))
    if name == "service.resume":
        return dump(services.holds.resume_service(inv.param("reason")))
    if name == "service.status":
        return {"ok": True}
    if name == "config.set":
        return dump(services.config.patch(dict(params.get("patch") or {})))
    if name == "event.publish":
        services.bus.publish(require(inv, "event"), dict(params.get("payload") or {}))
        return {"ok": True}
    if name == "backfill.start":
        services.backfill.start()
        return {"ok": True}
    if name == "backfill.stop":
        services.backfill.stop()
        return {"ok": True}
    if name == "stats.rebuild":
        return dump(services.stats.rebuild(inv.param("since")))
    if name == "stats.prune":
        return dump(services.retention.prune())
    if name == "notify":
        inv.log.info(
            "extension.notify",
            extension=inv.extension,
            message=str(inv.param("message", "")),
        )
        return {"ok": True}
    if name.startswith("timer."):
        return {"ok": True, "capability": name}
    if name.startswith(("daemon.", "backup.", "export", "import")):
        return {"ok": True, "capability": name, "note": "requires daemon control grant"}
    return {"ok": True, "capability": name}
