from __future__ import annotations

import sys
from pathlib import Path

import httpx

from downcroc.backup.bundle import BackupService
from downcroc.cli.context import load
from downcroc.domain.errors import BackupFailed, BackupInvalid, RestoreRefused
from downcroc.runtime.config.loader import ConfigError
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.service.lock import running


def _print_api(response: httpx.Response) -> int:
    if response.status_code >= 400:
        body = response.json()
        detail = body.get("message") if isinstance(body, dict) else response.text
        print(f"backup failed: {detail}", file=sys.stderr)
        return 1
    result = response.json()
    print(f"wrote {result['path']} ({result['files']} files, {result['bytes']} bytes)")
    return 0


def run(path: Path, include_logs: bool) -> int:
    try:
        paths, settings, _ = load()
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config error: {detail}", file=sys.stderr)
        return 1
    info = running(paths.service_file)
    if info is not None:
        try:
            response = httpx.post(
                f"{info.base_url}/api/backups",
                json={"path": str(path), "include_logs": include_logs},
                timeout=None,
            )
        except httpx.HTTPError as error:
            print(f"cannot reach downcroc: {error}", file=sys.stderr)
            return 1
        return _print_api(response)
    try:
        result = BackupService(paths, setup_logging(paths, settings)).create(
            path,
            include_logs=include_logs,
        )
    except (BackupFailed, BackupInvalid, RestoreRefused) as error:
        print(f"backup failed: {error}", file=sys.stderr)
        return 1
    print(f"wrote {result.path} ({result.files} files, {result.bytes} bytes)")
    return 0
