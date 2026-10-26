from __future__ import annotations

import sys
from pathlib import Path

from downcroc.backup.restore import (
    RestoreOutcome,
    RestoreService,
    log_outcome,
    perform_pending,
)
from downcroc.domain.errors import (
    BackupInvalid,
    RestoreFailed,
    RestorePending,
    RestoreRefused,
)
from downcroc.runtime.config.loader import ConfigError, load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import console, setup_logging
from downcroc.runtime.paths import Paths, ensure, resolve
from downcroc.runtime.service.lock import AlreadyRunning, InstanceLock


def _logger(paths: Paths):
    ensure(paths)
    try:
        settings, _ = load_or_create(paths.config_file)
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config warning: {detail}", file=sys.stderr)
        settings = Settings()
    return setup_logging(paths, settings, stream=sys.stderr)


def _show(outcome: RestoreOutcome | None) -> int:
    if outcome is None:
        print("nothing to restore", file=sys.stderr)
        return 1
    if outcome.status == "refused":
        detail = outcome.reason or "refused"
        print(f"restore refused: {detail}", file=sys.stderr)
        if outcome.revision:
            print(
                f"bundle revision {outcome.revision}, "
                f"current revision {outcome.current or 'none'}",
                file=sys.stderr,
            )
        return 1
    print(f"restored {outcome.bundle} ({outcome.files} files)")
    if outcome.previous_data is not None:
        print(f"previous data: {outcome.previous_data}")
    return 0


def run(path: Path) -> int:
    paths = resolve()
    lock = InstanceLock(paths.lock_file)
    try:
        lock.acquire()
    except AlreadyRunning:
        print("downcroc is running; stop it before restoring", file=sys.stderr)
        return 1
    try:
        resumed = paths.restore_marker.exists()
        if resumed:
            print("resuming the pending restore", file=sys.stderr)
        else:
            service = RestoreService(paths, console())
            try:
                service.request(path)
            except (BackupInvalid, RestoreRefused, RestorePending) as error:
                fields = getattr(error, "fields", None) or {}
                outcome = RestoreOutcome(
                    status="refused",
                    marker=paths.restore_marker,
                    bundle=path,
                    reason=fields.get("reason", str(error)),
                    revision=fields.get("revision"),
                    current=fields.get("current"),
                    failed_file=fields.get("file"),
                )
                log = _logger(paths)
                log_outcome(log, outcome)
                return _show(outcome)
        try:
            outcome = perform_pending(paths, resumed=resumed)
        except (RestoreFailed, OSError) as error:
            print(f"restore failed: {error}", file=sys.stderr)
            return 1
        log = _logger(paths)
        if outcome is not None:
            log_outcome(log, outcome)
        return _show(outcome)
    finally:
        lock.release()
