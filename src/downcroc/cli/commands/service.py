from __future__ import annotations

import sys
from dataclasses import asdict

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.progress import Progress
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime.service import install as service_install
from downcroc.runtime.service.lifecycle import start, status, stop
from downcroc.runtime.service.lock import AlreadyRunning

DEFINITION_WIDTH = 100


def _timeout(args: object, settings: object) -> float | None:
    value = getattr(args, "timeout", None)
    if value is None:
        return None
    ceiling = max(1.0, float(settings.daemon.start_timeout_s))
    return min(float(value), ceiling)


def _start(args: object, paths: object, settings: object, ui: Ui) -> int:
    progress = Progress(ui)
    try:
        info = start(
            paths,
            settings,
            timeout=_timeout(args, settings),
            progress=progress,
        )
    except AlreadyRunning as error:
        return _already(args, error)
    except (OSError, RuntimeError, TimeoutError) as error:
        raise CliError(
            str(error),
            code="service_start_failed",
            hint="inspect the log with `downcroc logs --since 5m`",
        ) from error
    finally:
        progress.done()
    if ui.json_mode:
        json_out({**asdict(info), "url": info.base_url})
        return 0
    record(
        {
            "daemon": f"running, pid {info.pid}, {info.base_url}",
        }
    )
    if not ui.quiet:
        print("next: downcroc vault unlock")
    return 0


def _already(args: object, error: AlreadyRunning) -> int:
    info = error.info
    ui = build(args)
    if ui.json_mode:
        json_out(
            {
                "state": "running",
                "pid": info.pid if info else None,
                "url": info.base_url if info else None,
                "changed": False,
            }
        )
        return 0
    if info is None:
        raise CliError(str(error), code="service_start_failed")
    record({"daemon": f"already running, pid {info.pid}, {info.base_url}"})
    return 0


def _stop(args: object, paths: object, settings: object, ui: Ui) -> int:
    stopped = stop(paths, settings)
    if ui.json_mode:
        json_out({"state": "stopped", "changed": stopped})
        return 0
    if stopped:
        record({"daemon": "stopped"})
    else:
        record({"daemon": "not running"})
    return 0


def _restart(args: object, paths: object, settings: object, ui: Ui) -> int:
    stop(paths, settings)
    return _start(args, paths, settings, ui)


def _install(args: object, paths: object, settings: object, ui: Ui) -> int:
    try:
        installed = service_install.install(paths, settings, print_only=args.print_only)
    except (OSError, RuntimeError) as error:
        raise CliError(
            str(error),
            code="service_install_failed",
            hint="run `downcroc service install --print` to inspect the unit",
        ) from error
    if args.print_only:
        if ui.json_mode:
            json_out(installed)
        else:
            sys.stdout.write(installed["definition"])
        return 0
    if ui.json_mode:
        json_out(installed)
        return 0
    record({"service": f"installed ({installed['kind']}), {installed['path']}"})
    if not ui.quiet:
        print("next: downcroc service start")
    return 0


def _uninstall(args: object, paths: object, settings: object, ui: Ui) -> int:
    try:
        removed = service_install.uninstall(paths, settings)
    except (OSError, RuntimeError) as error:
        raise CliError(
            str(error),
            code="service_uninstall_failed",
            hint="check that the service manager is available",
        ) from error
    if ui.json_mode:
        json_out(removed)
        return 0
    if removed["removed"]:
        record({"service": f"uninstalled ({removed['kind']}), {removed['path']}"})
    else:
        record({"service": f"not installed ({removed['kind']})"})
    print("data stays at the paths printed by `downcroc status`")
    return 0


def _status(args: object, paths: object, ui: Ui) -> int:
    report = status(paths)
    healthy = report.get("state") == "running"
    if ui.json_mode:
        json_out(report)
        return 0 if healthy else 1
    if report.get("state") == "stopped":
        record({"daemon": "stopped"})
        if not ui.quiet:
            print("next: downcroc service start")
        return 1
    if report.get("state") == "stale":
        record({"daemon": f"stale, pid {report['pid']} is gone"})
        if not ui.quiet:
            print("next: downcroc service start")
        return 1
    if report.get("state") == "unreachable":
        record(
            {"daemon": f"pid {report['pid']} on port {report['port']} is not answering"}
        )
        if not ui.quiet:
            print("next: downcroc logs --since 5m")
        return 1
    lines = {
        "daemon": f"running, pid {report['pid']}, {report['url']}",
        "version": report.get("version"),
        "started_at": report.get("started_at"),
        "uptime_s": report.get("uptime_s"),
    }
    with api(paths) as client:
        sending = get(client, "/api/status").get("sending") or {}
    if sending.get("state") == "paused":
        lines["sending"] = (
            f"paused since {sending.get('since') or '-'}"
            f", until {sending.get('until') or 'resume'}"
            f" ({sending.get('reason') or 'no reason'})"
        )
    else:
        lines["sending"] = "running"
    record(lines)
    return 0


def start_now(args: object):
    paths, settings, _ = load()
    return _start(args, paths, settings, build(args))


def install_now(args: object):
    paths, settings, _ = load()
    try:
        return service_install.install(paths, settings, print_only=False)
    except OSError, RuntimeError:
        return None


def _pause(args: object, paths: object, ui: Ui) -> int:
    report = status(paths)
    if report.get("state") != "running":
        raise CliError(
            "the daemon is not running",
            code="daemon_not_running",
            hint="a stopped daemon sends nothing; start it first if the hold must outlive the stop",
        )
    body = {
        "reason": getattr(args, "reason", None),
        "for_s": getattr(args, "for_s", None),
    }
    with api(paths) as client:
        result = post(client, "/api/service/pause", body)
    if ui.json_mode:
        json_out(result)
        return 0
    sending = result["sending"]
    detail = "sending paused"
    if sending.get("until"):
        detail += f" until {sending['until']}"
    if sending.get("reason"):
        detail += f" ({sending['reason']})"
    record({"sending": detail, "changed": result.get("changed")})
    return 0


def _resume(args: object, paths: object, ui: Ui) -> int:
    with api(paths) as client:
        result = post(
            client, "/api/service/resume", {"reason": getattr(args, "reason", None)}
        )
    if ui.json_mode:
        json_out(result)
        return 0
    record({"sending": "running", "changed": result.get("changed")})
    return 0


def run(args: object) -> int:
    paths, settings, _ = load()
    ui = build(args)
    action = getattr(args, "action", None)
    if action is None:
        if open_menu(ui, "service_menu"):
            return 0
        action = "status"
    if action == "start":
        return _start(args, paths, settings, ui)
    if action == "stop":
        return _stop(args, paths, settings, ui)
    if action == "restart":
        return _restart(args, paths, settings, ui)
    if action == "pause":
        return _pause(args, paths, ui)
    if action == "resume":
        return _resume(args, paths, ui)
    if action == "install":
        return _install(args, paths, settings, ui)
    if action == "uninstall":
        return _uninstall(args, paths, settings, ui)
    return _status(args, paths, ui)
