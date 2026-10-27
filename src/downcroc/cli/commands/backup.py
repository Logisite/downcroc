from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from downcroc.backup.bundle import BackupService
from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build
from downcroc.domain.errors import BackupFailed, BackupInvalid, RestoreRefused
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.service.lock import running

NAME = "downcroc-{stamp}.tar.zst"
DEFAULT_DIR = "downcroc-backups"


def _name() -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return NAME.format(stamp=stamp)


def _target(path: str | None, paths, ui: Ui) -> Path:
    if path is None:
        directory = paths.data.parent / DEFAULT_DIR
        directory.mkdir(parents=True, exist_ok=True)
        return directory / _name()
    target = path_tools.expand(path)
    text = str(path)
    if target.is_dir() or text.endswith(os.sep):
        return target / _name()
    if not target.parent.is_dir():
        raise CliError(
            "the parent directory does not exist",
            code="input_invalid",
            fields={"path": str(target.parent)},
            hint="create it first",
        )
    return target


def _check_overwrite(target: Path, force: bool, ui: Ui) -> None:
    if not target.exists() or force:
        return
    if ui.interactive and prompts.confirm(f"overwrite {target}?", ui=ui, default=False):
        return
    raise CliError(
        "the backup already exists",
        code="target_exists",
        fields={"path": str(target)},
        hint="pass --force to overwrite it",
    )


def _missing_database(paths) -> CliError:
    database = paths.data / "downcroc.db"
    return CliError(
        "the database does not exist yet",
        code="no_database",
        fields={"path": str(database)},
        hint="start the daemon once with `downcroc service start`, then back up",
    )


def _create(paths, settings, target: Path, include_logs: bool) -> dict:
    if running(paths.service_file) is not None:
        with api(paths) as client:
            return post(
                client,
                "/api/backups",
                {"path": str(target), "include_logs": include_logs},
            )
    try:
        created = BackupService(
            paths,
            setup_logging(paths, settings),
        ).create(target, include_logs=include_logs)
    except (BackupFailed, BackupInvalid, RestoreRefused) as error:
        fields = getattr(error, "fields", None) or {}
        raise CliError(
            str(error),
            code="backup_failed",
            fields=fields,
            hint="inspect `downcroc logs --since 5m`",
        ) from error
    return {
        "path": str(created.path),
        "files": created.files,
        "bytes": created.bytes,
        "duration_ms": created.duration_ms,
        "schema_revision": created.manifest.schema_revision,
        "counts": created.manifest.counts,
    }


def run(args: object) -> int:
    ui = build(args)
    paths, settings, _ = load()
    target = _target(getattr(args, "path", None), paths, ui)
    _check_overwrite(target, bool(getattr(args, "force", False)), ui)
    if not (paths.data / "downcroc.db").is_file():
        raise _missing_database(paths)
    if not ui.json_mode:
        print(f"writing {target}")
    result = _create(
        paths,
        settings,
        target,
        bool(getattr(args, "include_logs", False)),
    )
    if ui.json_mode:
        json_out(result)
        return 0
    record(
        {
            "backup": result["path"],
            "files": result["files"],
            "bytes": result["bytes"],
        }
    )
    if not ui.quiet:
        print(f"next: downcroc restore {result['path']} --dry-run")
    return 0
