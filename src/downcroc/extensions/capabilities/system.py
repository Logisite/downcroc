from __future__ import annotations

import shlex
import subprocess
import sys
from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require
from downcroc.extensions.tiers import tier_for
from downcroc.runtime.paths import resolve
from downcroc.runtime.service import token as service_token


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
        "notify.system",
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
        "capability.list",
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
    if name == "notify.system":
        return notify_system(inv, params)
    if name == "capability.list":
        return [
            {"name": item, "tier": tier_for(item)} for item in inv.broker.capabilities
        ]
    if name == "cli.run":
        return run_cli(inv, params)
    if name.startswith("timer."):
        return {"ok": True, "capability": name}
    if name.startswith(("daemon.", "backup.", "export", "import")):
        return {"ok": True, "capability": name, "note": "requires daemon control grant"}
    return {"ok": True, "capability": name}


def run_cli(inv: Invocation, params: dict[str, Any]) -> dict[str, Any]:
    argv = params.get("argv")
    if isinstance(argv, str):
        argv = shlex.split(argv)
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
    ):
        raise ValueError("argv must be a non-empty list of strings")
    result = subprocess.run(
        [sys.executable, "-m", "downcroc", *argv],
        capture_output=True,
        text=True,
        timeout=inv.settings.call_timeout_s,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": _redact(result.stdout),
        "stderr": _redact(result.stderr),
    }


def notify_system(inv: Invocation, params: dict[str, Any]) -> dict[str, Any]:
    command = list(inv.settings.notifier)
    if not command:
        return {"ok": False, "error": "notify_unavailable"}
    title = str(params.get("title", "downcroc"))
    message = str(params.get("message", ""))
    result = subprocess.run(
        [*command, title, message],
        capture_output=True,
        text=True,
        timeout=inv.settings.call_timeout_s,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:2000],
    }


def _redact(text: str) -> str:
    secret = service_token.read(resolve().token_file)
    if secret:
        text = text.replace(secret, "[redacted]")
    return text[:8000]
