from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from downcroc.backup.bundle import BackupService
from downcroc.cli.client import api, post
from downcroc.cli.context import load
from downcroc.domain.errors import BackupFailed, BackupInvalid, RestoreRefused
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.service.lock import running


def _target(path: Path | None) -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    name = f"downcroc-{stamp}.tar.zst"
    if path is None:
        return Path.cwd() / name
    path = path.expanduser()
    text = str(path)
    if path.is_dir() or text.endswith(os.sep):
        return path / name
    return path


def run(path: Path | None, include_logs: bool) -> int:
    paths, settings, _ = load()
    target = _target(path)
    if running(paths.service_file) is not None:
        with api(paths) as client:
            result = post(
                client,
                "/api/backups",
                {"path": str(target), "include_logs": include_logs},
            )
    else:
        try:
            created = BackupService(
                paths,
                setup_logging(paths, settings),
            ).create(
                target,
                include_logs=include_logs,
            )
        except (BackupFailed, BackupInvalid, RestoreRefused) as error:
            print(f"backup failed: {error}", file=sys.stderr)
            return 1
        result = {
            "path": str(created.path),
            "files": created.files,
            "bytes": created.bytes,
        }
    print(f"wrote {result['path']} ({result['files']} files, {result['bytes']} bytes)")
    return 0
