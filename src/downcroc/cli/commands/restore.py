from __future__ import annotations

import sys
from pathlib import Path

from downcroc.backup.manifest import Manifest
from downcroc.backup.restore import (
    RestoreOutcome,
    RestoreService,
    log_outcome,
    perform_pending,
)
from downcroc.backup.verify import verify_bundle
from downcroc.cli import paths as path_tools
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.progress import Progress
from downcroc.cli.ui.session import Ui, build
from downcroc.domain.errors import (
    BackupInvalid,
    RestoreFailed,
    RestorePending,
    RestoreRefused,
)
from downcroc.runtime.config.loader import ConfigError, load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.paths import Paths, ensure
from downcroc.runtime.service import lifecycle
from downcroc.runtime.service.lock import AlreadyRunning, InstanceLock, running

COUNTS = ("accounts", "batches", "jobs", "messages", "threads")


def _logger(paths: Paths):
    ensure(paths)
    try:
        settings, _ = load_or_create(paths.config_file)
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config warning: {detail}", file=sys.stderr)
        settings = Settings()
    return setup_logging(paths, settings, stream=sys.stderr)


def _size(value: int) -> str:
    if value < 1024:
        return f"{value} bytes"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _summary(source: Path, manifest: Manifest) -> dict:
    counts = {name: manifest.counts.get(name, 0) for name in COUNTS}
    logs = any(name.startswith("logs/") for name in manifest.files)
    return {
        "bundle": str(source),
        "created": manifest.created_at,
        "version": manifest.app_version,
        "revision": manifest.schema_revision,
        "hostname": manifest.hostname,
        "size": source.stat().st_size,
        "size_text": _size(source.stat().st_size),
        "files": len(manifest.files),
        "counts": counts,
        "logs": logs,
    }


def _print_manifest(summary: dict) -> None:
    print(f"Bundle {summary['bundle']}")
    record(
        {
            "created": summary["created"],
            "version": summary["version"],
            "schema": summary["revision"],
            "host": summary["hostname"],
            "size": f"{summary['size_text']} in {summary['files']} files",
            "accounts": summary["counts"]["accounts"],
            "batches": summary["counts"]["batches"],
            "jobs": summary["counts"]["jobs"],
            "messages": summary["counts"]["messages"],
            "threads": summary["counts"]["threads"],
            "logs": "included" if summary["logs"] else "not included",
        },
    )


def _refusal(error: Exception, source: Path) -> CliError:
    fields = getattr(error, "fields", None) or {}
    details = dict(fields)
    details["bundle"] = str(source)
    if isinstance(error, RestoreRefused):
        return CliError(
            getattr(error, "message", str(error)),
            code="restore_refused",
            fields=details,
            hint="use a bundle written by this version of downcroc",
        )
    return CliError(
        getattr(error, "message", str(error)),
        code="backup_invalid",
        fields=details,
        hint="the bundle is damaged or incomplete; try another copy",
    )


def _log_refused(log, error: Exception) -> None:
    fields = getattr(error, "fields", None) or {}
    log.warning(
        "restore.refused",
        revision=fields.get("revision", "none"),
        current=fields.get("current", "none"),
        reason=fields.get("reason", getattr(error, "message", str(error))),
    )


def _verify(source: Path, log) -> Manifest:
    try:
        return verify_bundle(source, log)
    except (BackupInvalid, RestoreRefused) as error:
        _log_refused(log, error)
        raise _refusal(error, source) from error


def _confirm(ui: Ui, paths: Paths, args: object) -> None:
    print()
    print(f"This replaces the current data at {paths.data}.")
    print("The current data is moved beside it with a .bak-<timestamp> suffix.")
    prompts.confirm_word(
        "restore",
        "Restoring replaces every account, batch, job, message, and setting.",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )


def _outcome_body(outcome: RestoreOutcome) -> dict:
    return {
        "status": outcome.status,
        "bundle": str(outcome.bundle) if outcome.bundle else None,
        "files": outcome.files,
        "counts": outcome.counts,
        "revision": outcome.revision,
        "previous_data": str(outcome.previous_data) if outcome.previous_data else None,
        "previous_config": (
            str(outcome.previous_config) if outcome.previous_config else None
        ),
        "reason": outcome.reason,
        "resumed": outcome.resumed,
    }


def _show(outcome: RestoreOutcome | None, ui: Ui) -> int:
    if outcome is None:
        raise CliError("nothing to restore", code="restore_pending")
    if outcome.status == "refused":
        raise CliError(
            outcome.reason or "the bundle was refused",
            code="restore_refused",
            fields={"bundle": str(outcome.bundle or "unknown")},
        )
    if ui.json_mode:
        json_out(_outcome_body(outcome))
        return 0
    record(
        {
            "restored": str(outcome.bundle or "unknown"),
            "files": outcome.files,
            "accounts": outcome.counts.get("accounts", 0),
            "batches": outcome.counts.get("batches", 0),
            "jobs": outcome.counts.get("jobs", 0),
            "previous data": (
                str(outcome.previous_data) if outcome.previous_data else "none"
            ),
        },
    )
    return 0


def _swap(
    paths: Paths,
    source: Path | None,
    manifest: Manifest | None,
    log,
    *,
    resumed: bool,
) -> RestoreOutcome | None:
    lock = InstanceLock(paths.lock_file)
    try:
        lock.acquire()
    except AlreadyRunning as error:
        raise CliError(
            "downcroc is running",
            code="daemon_running",
            hint="stop it with `downcroc service stop`, or pass --stop",
        ) from error
    try:
        if not resumed:
            assert source is not None
            service = RestoreService(paths, log)
            try:
                service.request(source, manifest=manifest)
            except RestorePending as error:
                raise CliError(
                    "a restore is already pending",
                    code="restore_pending",
                    hint="start the daemon once to finish the pending restore",
                ) from error
            except (BackupInvalid, RestoreRefused) as error:
                _log_refused(log, error)
                raise _refusal(error, source) from error
        try:
            outcome = perform_pending(paths, resumed=resumed)
        except (RestoreFailed, OSError) as error:
            raise CliError(
                getattr(error, "message", str(error)),
                code="restore_failed",
                fields=getattr(error, "fields", None) or {},
                hint="the previous data is kept; inspect `downcroc logs --since 5m`",
            ) from error
        if outcome is not None:
            log_outcome(log, outcome)
        return outcome
    finally:
        lock.release()


def _restart(paths: Paths, settings: Settings, ui: Ui) -> None:
    if ui.json_mode:
        return
    print("restarting the daemon", file=sys.stderr)
    progress = Progress(ui)
    try:
        lifecycle.start(paths, settings, progress=progress)
    finally:
        progress.done()


def _settings(paths: Paths) -> Settings:
    try:
        return load_or_create(paths.config_file)[0]
    except ConfigError:
        return Settings()


def run(args: object) -> int:
    ui = build(args)
    paths, settings, _ = load()
    source = path_tools.expand(getattr(args, "path", ""))
    log = _logger(paths)

    if paths.restore_marker.exists():
        if not ui.json_mode and not ui.quiet:
            print("resuming the pending restore", file=sys.stderr)
        outcome = _swap(paths, None, None, log, resumed=True)
        return _show(outcome, ui)

    source = path_tools.resolve_input(source, field="bundle")
    manifest = _verify(source, log)
    summary = _summary(source, manifest)
    if ui.json_mode and args.dry_run:
        json_out(summary)
        return 0
    if not ui.json_mode:
        _print_manifest(summary)
    if args.dry_run:
        return 0

    was_running = running(paths.service_file) is not None
    if was_running and not getattr(args, "stop", False):
        raise CliError(
            "downcroc is running",
            code="daemon_running",
            hint="stop it with `downcroc service stop`, or pass --stop",
        )
    _confirm(ui, paths, args)
    if was_running:
        lifecycle.stop(paths, settings)

    try:
        outcome = _swap(paths, source, manifest, log, resumed=False)
    finally:
        if was_running:
            _restart(paths, _settings(paths), ui)
    return _show(outcome, ui)
