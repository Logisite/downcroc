from __future__ import annotations

import time
from pathlib import Path

from downcroc.cli.client import api, get
from downcroc.cli.commands.doctor_transports import capacity as doctor_capacity
from downcroc.cli.commands.doctor_transports import inbound as doctor_inbound
from downcroc.cli.commands.doctor_transports import transports as doctor_transports
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import run_args
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime import keyring
from downcroc.runtime.config.loader import ConfigError
from downcroc.runtime.paths import resolve
from downcroc.runtime.service import install as service_install
from downcroc.runtime.service.lifecycle import status
from downcroc.version import __version__

LOG_TAIL_S = 300


def _age(path: Path) -> str:
    if not path.is_file():
        return "missing"
    seconds = max(0, int(time.time() - path.stat().st_mtime))
    if seconds < 60:
        return f"last write {seconds}s ago"
    if seconds < 3600:
        return f"last write {seconds // 60}m ago"
    return f"last write {seconds // 3600}h ago"


def _checks(args: object, ui: Ui) -> list[dict]:
    paths, settings, _ = load()
    report = status(paths)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, fix: str = "") -> None:
        checks.append({"check": name, "ok": ok, "detail": detail, "fix": fix})

    add("config parses", True, str(paths.config_file))
    writable = all(_writable(path) for path in (paths.config, paths.data, paths.state))
    add(
        "paths writable",
        writable,
        f"{paths.config}, {paths.data}, {paths.state}",
        "fix the directory permissions",
    )
    add(
        "database",
        (paths.data / "downcroc.db").is_file(),
        str(paths.data / "downcroc.db"),
        "run downcroc service start, which runs migrations",
    )
    state = report.get("state")
    add(
        "daemon alive",
        state == "running",
        f"{state}, pid {report.get('pid', '-')}",
        "run downcroc service start",
    )
    add(
        "service definition",
        service_install.installed(paths),
        "installed" if service_install.installed(paths) else "not installed",
        "run downcroc service install",
    )
    add("log", True, f"{paths.log_file}, {_age(paths.log_file)}")
    store = keyring.describe()
    add(
        "credential store",
        True,
        keyring.status() if store.available else f"unavailable ({store.reason})",
        "",
    )
    if state == "running":
        checks.extend(_remote(args, ui))
    else:
        add(
            "health reachable", False, "daemon is not running", "downcroc service start"
        )
    add("version", True, __version__)
    del settings
    return checks


def _remote(args: object, ui: Ui) -> list[dict]:
    del ui
    paths, _, _ = load()
    checks: list[dict] = []
    try:
        with api(paths, timeout=getattr(args, "timeout", None)) as client:
            status_body = get(client, "/api/status")
            vault = get(client, "/api/vault")
            accounts = get(client, "/api/accounts")
            providers = get(client, "/api/providers")
    except CliError as error:
        checks.append(
            {
                "check": "health reachable",
                "ok": False,
                "detail": error.label,
                "fix": "downcroc logs --since 5m",
            }
        )
        return checks
    checks.append(
        {
            "check": "api token accepted",
            "ok": True,
            "detail": f"downcroc {status_body['version']}",
            "fix": "",
        }
    )
    checks.append(
        {
            "check": "vault state",
            "ok": vault["state"] == "unlocked",
            "detail": vault["state"],
            "fix": "downcroc vault unlock",
        }
    )
    broken = [item for item in accounts if item["status"] == "needs_reauth"]
    checks.append(
        {
            "check": "accounts",
            "ok": not broken,
            "detail": f"{len(accounts)} total, {len(broken)} need re-auth",
            "fix": "downcroc account",
        }
    )
    unready = [item for item in providers if not item["ready"]]
    providers_ok = all(
        item["ready"] or item["source"] is None or _builtin(item) for item in unready
    )
    checks.append(
        {
            "check": "provider readiness",
            "ok": providers_ok or bool(accounts),
            "detail": ", ".join(
                f"{item['id']}: {', '.join(item['missing'])}" for item in unready
            )
            or "every provider ready",
            "fix": "downcroc provider list",
        }
    )
    return checks


def _builtin(item: dict) -> bool:
    return item["missing"] in (
        ["oauth_client_id", "oauth_client_secret"],
        ["imap_host", "smtp_host"],
    )


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return path.is_dir()


def _doctor_remote(selected: str, args: object, ui: Ui) -> int:
    paths, _, _ = load()
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        if selected == "transports":
            return doctor_transports(client, ui)
        if selected == "inbound":
            return doctor_inbound(client, ui)
        return doctor_capacity(client, ui)


def doctor(args: object, ui: Ui) -> int:
    selected = getattr(args, "doctor_command", None)
    if selected in {"transports", "capacity", "inbound"}:
        return _doctor_remote(selected, args, ui)
    checks = _checks(args, ui)
    failed = [item for item in checks if not item["ok"]]
    if ui.json_mode:
        json_out({"ok": not failed, "checks": checks})
        return 1 if failed else 0
    for item in checks:
        tag = f"{ui.glyph('ok' if item['ok'] else 'fail'):<6}"
        print(f"{tag} {item['check']:<22} {item['detail']}")
        if not item["ok"] and item["fix"]:
            print(f"       fix: {item['fix']}")
    print()
    if failed:
        print(f"{len(failed)} of {len(checks)} checks need attention")
        return 1
    print("every check passed")
    return 0


def status_report(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    report = status(paths)
    running = report.get("state") == "running"
    if ui.json_mode:
        body = _body(args, report, running)
        json_out(body)
        return 0 if running else 1
    _print_body(args, report, running)
    return 0 if running else 1


def _body(args: object, report: dict, running: bool) -> dict:
    body: dict = {"daemon": report}
    if not running:
        return body
    paths, _, _ = load()
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        body["vault"] = get(client, "/api/vault")
        body["accounts"] = get(client, "/api/accounts")
        body["summary"] = get(client, "/api/stats/summary")
        body["failed"] = get(client, "/api/failed", limit=1)
    body["log"] = {"path": str(paths.log_file), "age": _age(paths.log_file)}
    return body


def _print_body(args: object, report: dict, running: bool) -> None:
    paths, _, _ = load()
    lines: dict[str, str] = {}
    if running:
        lines["daemon"] = f"running, pid {report['pid']}, {report['url']}"
    elif report.get("state") == "stopped":
        lines["daemon"] = "stopped, run: downcroc service start"
    else:
        lines["daemon"] = f"{report.get('state')}, run: downcroc service start"
    lines["paths"] = f"config {paths.config}, data {paths.data}"
    lines["log"] = f"{paths.log_file}, {_age(paths.log_file)}"
    if running:
        with api(paths, timeout=getattr(args, "timeout", None)) as client:
            vault = get(client, "/api/vault")
            accounts = get(client, "/api/accounts")
            summary = get(client, "/api/stats/summary")
            failed = get(client, "/api/failed", limit=1)
        lines["vault"] = vault["state"]
        broken = [item for item in accounts if item["status"] == "needs_reauth"]
        pending = [item for item in accounts if item["status"] == "pending"]
        detail = f"{len(accounts)} total"
        if broken:
            detail += f", {len(broken)} needs re-auth, run: downcroc account connect"
        if pending:
            detail += f", {len(pending)} pending"
        lines["accounts"] = detail
        total = summary["total"]
        lines["queue"] = f"{total.get('sent', 0)} sent, {total.get('failed', 0)} failed"
        if failed:
            lines["failed"] = f"{failed[0]['recipient']} {failed[0]['code']}"
    record(lines)


def run(args: object) -> int:
    ui = build(args)
    command = getattr(args, "command", None)
    if command == "doctor":
        return doctor(args, ui)
    if command == "status":
        return status_report(args, ui)
    return home(args, ui)


def _absent(args: object, ui: Ui, paths: object) -> int:
    if ui.json_mode:
        json_out({"state": "absent", "config": str(paths.config_file)})
        return 1
    print(f"{ui.accent(ui.glyph('mail'))} {ui.bold('downcroc')} {__version__}")
    print(f"  {ui.paint(f'no installation found at {paths.config}', 'warn')}")
    if not ui.interactive:
        print(f"  {ui.dim('next: downcroc init')}")
        return 1
    print()
    if not prompts.confirm("Run init now?", ui=ui, default=True):
        return 0
    return run_args(ui, "init")


def _state(args: object, paths: object) -> dict:
    report = status(paths)
    info: dict = {"report": report, "running": report.get("state") == "running"}
    if not info["running"]:
        return info
    try:
        with api(paths, timeout=getattr(args, "timeout", None)) as client:
            info["vault"] = get(client, "/api/vault")
            info["accounts"] = get(client, "/api/accounts")
            info["summary"] = get(client, "/api/stats/summary")
    except CliError:
        info["running"] = False
    return info


def _home_header(ui: Ui, info: dict) -> None:
    report = info["report"]
    running = info["running"]
    where = f"daemon running, pid {report['pid']}" if running else "daemon stopped"
    print(
        f"{ui.accent(ui.glyph('mail'))} {ui.bold('downcroc')} {__version__}   {ui.dim(where)}"
    )
    if not running:
        print(f"  {ui.dim('next: downcroc service start')}")
        print()
        return
    vault = info.get("vault")
    accounts = info.get("accounts") or []
    summary = info.get("summary") or {}
    total = summary.get("total", {})
    tone = "good" if vault and vault["state"] == "unlocked" else "warn"
    pending = [item for item in accounts if item["status"] == "pending"]
    queue = f"{total.get('sent', 0):,} sent, {total.get('failed', 0):,} failed"
    detail = f"{len(accounts):,} accounts"
    if pending:
        detail += f", {len(pending):,} pending"
    state = "vault " + (vault["state"] if vault else "unknown")
    print(f"  {ui.paint(state, tone)}   {detail}   {queue}")
    print()


def _needs_vault(info: dict) -> str | None:
    vault = info.get("vault")
    if vault is None or vault["state"] == "unlocked":
        return None
    return "unlock" if Path(vault["path"]).exists() else "init"


def _prompt_step(ui: Ui, info: dict) -> tuple[str, list[str]] | None:
    if not info["running"]:
        return "Start the daemon now?", ["service", "start"]
    vault_step = _needs_vault(info)
    if vault_step == "unlock":
        return "Unlock now?", ["vault", "unlock"]
    if vault_step == "init":
        return "Create the vault now?", ["vault", "init"]
    if not info.get("accounts"):
        return "Add an account now?", ["account", "add"]
    return None


def home(args: object, ui: Ui) -> int:
    paths = resolve()
    if not paths.config_file.exists():
        return _absent(args, ui, paths)
    if not ui.interactive:
        return status_report(args, ui)
    while True:
        info = _state(args, paths)
        _home_header(ui, info)
        step = _prompt_step(ui, info)
        if step is None:
            break
        question, argv = step
        if not prompts.confirm(question, ui=ui, default=True):
            return 0
        code = run_args(ui, *argv)
        if code != 0:
            return code
    from downcroc.cli.ui.menus import home_menu

    try:
        home_menu(ui)
    except CliError as error:
        if error.code != "cancelled":
            raise
    return 0


def config_error(error: ConfigError) -> CliError:
    detail = f"{error.field}: {error}" if error.field else str(error)
    return CliError(detail, code="config_invalid", hint="run downcroc config show")
