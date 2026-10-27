from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from downcroc.backup.fsops import sync_dir
from downcroc.backup.manifest import Manifest
from downcroc.backup.pending import (
    MarkerError,
    RestoreMarker,
    read_marker,
    remove_marker,
    request_marker,
    write_marker,
)
from downcroc.backup.stage import discard_stage, stage_bundle
from downcroc.backup.verify import verify_bundle
from downcroc.domain.errors import (
    BackupInvalid,
    RestoreFailed,
    RestorePending,
    RestoreRefused,
)
from downcroc.runtime.fs import replace as replace_path
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


@dataclass(frozen=True)
class RestoreOutcome:
    status: Literal["pending", "restored", "refused"]
    marker: Path
    bundle: Path | None = None
    resumed: bool = False
    files: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    revision: str | None = None
    current: str | None = None
    previous_data: Path | None = None
    previous_config: Path | None = None
    duration_ms: int = 0
    reason: str | None = None
    failed_file: str | None = None


class RestoreService:
    def __init__(self, paths: Paths, log: EventLogger) -> None:
        self._paths = paths
        self._log = log

    def request(self, bundle: Path, manifest: Manifest | None = None) -> RestoreOutcome:
        if self._paths.restore_marker.exists():
            raise RestorePending("a restore is already pending")
        source = bundle.expanduser().absolute()
        if manifest is None:
            try:
                manifest = verify_bundle(source, self._log)
            except RestoreRefused as error:
                _log_refused(self._log, error)
                raise
        write_marker(self._paths.restore_marker, request_marker(source))
        return RestoreOutcome(
            status="pending",
            marker=self._paths.restore_marker,
            bundle=source,
            files=len(manifest.files),
            counts=manifest.counts,
            revision=manifest.schema_revision,
        )


def perform_pending(paths: Paths, resumed: bool = True) -> RestoreOutcome | None:
    marker_path = paths.restore_marker
    if not marker_path.exists():
        return None
    started = time.monotonic()
    try:
        marker = read_marker(marker_path)
    except MarkerError as error:
        remove_marker(marker_path)
        return RestoreOutcome(
            status="refused",
            marker=marker_path,
            resumed=resumed,
            reason=str(error),
        )
    bundle = Path(marker.bundle)
    try:
        manifest = verify_bundle(bundle)
    except BackupInvalid as error:
        _recover_live(paths, marker)
        remove_marker(marker_path)
        return RestoreOutcome(
            status="refused",
            marker=marker_path,
            bundle=bundle,
            resumed=resumed,
            reason=error.message,
            failed_file=(error.fields or {}).get("file"),
        )
    except RestoreRefused as error:
        _recover_live(paths, marker)
        remove_marker(marker_path)
        return _refused(marker_path, bundle, resumed, error)

    stage_data = _optional(marker.stage_data)
    stage_config = _optional(marker.stage_config)
    previous_data = _optional(marker.previous_data)
    previous_config = _optional(marker.previous_config)
    stage_exists = stage_data is not None and stage_data.is_dir()
    live_ready = (paths.data / "downcroc.db").is_file()
    data_done = (
        live_ready
        and not stage_exists
        and (
            (previous_data is not None and previous_data.exists())
            or marker.phase == "staged"
        )
    )
    if data_done:
        try:
            previous_config = _finish_config(
                paths, marker_path, marker, stage_config, previous_config
            )
        except OSError as error:
            raise RestoreFailed(
                "config swap failed",
                fields={"path": str(paths.config)},
            ) from error
        remove_marker(marker_path)
        return _restored(
            marker_path,
            bundle,
            resumed,
            manifest,
            started,
            previous_data,
            previous_config,
        )

    counts = manifest.counts
    if not stage_exists or stage_config is None or not stage_config.is_dir():
        stage = stage_bundle(bundle, manifest, paths)
        stage_data = stage.data
        stage_config = stage.config
        counts = stage.counts
    stamp = _stamp()
    if paths.data.exists():
        previous_data = _unique(paths.data.with_name(f"{paths.data.name}.bak-{stamp}"))
    elif previous_data is None or not previous_data.exists():
        previous_data = None
    if (
        stage_config is not None
        and any(stage_config.iterdir())
        and paths.config.exists()
    ):
        previous_config = _unique(
            paths.config.with_name(f"{paths.config.name}.bak-{stamp}")
        )
    staged = replace(
        marker,
        phase="staged",
        stage_data=str(stage_data),
        stage_config=str(stage_config),
        previous_data=str(previous_data) if previous_data else None,
        previous_config=str(previous_config) if previous_config else None,
    )
    write_marker(marker_path, staged)
    try:
        if paths.data.exists():
            replace_path(paths.data, previous_data)
        if stage_data is None or not stage_data.exists():
            raise RestoreFailed(
                "staged data is missing",
                fields={"path": str(stage_data)},
            )
        replace_path(stage_data, paths.data)
        sync_dir(paths.data.parent)
    except (OSError, RestoreFailed) as error:
        _rollback_data(paths, previous_data)
        if isinstance(error, RestoreFailed):
            raise
        raise RestoreFailed(
            "data swap failed",
            fields={"path": str(paths.data), "reason": str(error)},
        ) from error

    try:
        previous_config = _swap_config(paths, stage_config, previous_config, stamp)
    except OSError as error:
        raise RestoreFailed(
            "config swap failed",
            fields={"path": str(paths.config)},
        ) from error
    remove_marker(marker_path)
    if stage_data is not None:
        discard_stage(stage_data, stage_config)
    return _restored(
        marker_path,
        bundle,
        resumed,
        manifest,
        started,
        previous_data,
        previous_config,
        counts,
    )


def log_outcome(log: EventLogger, outcome: RestoreOutcome) -> None:
    if outcome.status == "restored":
        log.info(
            "restore.staged",
            path=str(outcome.bundle or "unknown"),
            files=outcome.files,
        )
        log.info(
            "restore.swapped",
            previous=str(outcome.previous_data or "none"),
            duration_ms=outcome.duration_ms,
        )
        if outcome.resumed:
            log.info("restore.resumed", marker=str(outcome.marker))
        return
    if outcome.status == "refused":
        if outcome.failed_file:
            log.warning("backup.verify_failed", file=outcome.failed_file)
        log.warning(
            "restore.refused",
            revision=outcome.revision or "none",
            current=outcome.current or "none",
            reason=outcome.reason or "refused",
        )


def _optional(value: str | None) -> Path | None:
    return Path(value) if value else None


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}-{index}")
        if not candidate.exists():
            return candidate
    raise RestoreFailed(
        "cannot choose a backup directory name",
        fields={"path": str(path)},
    )


def _rollback_data(paths: Paths, previous: Path | None) -> None:
    if previous is None or not previous.exists() or paths.data.exists():
        return
    try:
        replace_path(previous, paths.data)
        sync_dir(paths.data.parent)
    except OSError:
        return


def _recover_live(paths: Paths, marker: RestoreMarker) -> None:
    previous_data = _optional(marker.previous_data)
    if not paths.data.exists() and previous_data and previous_data.exists():
        replace_path(previous_data, paths.data)
        sync_dir(paths.data.parent)
    previous_config = _optional(marker.previous_config)
    if not paths.config.exists() and previous_config and previous_config.exists():
        replace_path(previous_config, paths.config)
        sync_dir(paths.config.parent)
    stage_data = _optional(marker.stage_data)
    stage_config = _optional(marker.stage_config)
    discard_stage(stage_data, stage_config)


def _swap_config(
    paths: Paths,
    stage_config: Path | None,
    previous_config: Path | None,
    stamp: str,
) -> Path | None:
    if (
        stage_config is not None
        and stage_config.is_dir()
        and any(stage_config.iterdir())
    ):
        if paths.config.exists():
            chosen = previous_config
            if chosen is None or chosen.exists():
                chosen = _unique(
                    paths.config.with_name(f"{paths.config.name}.bak-{stamp}")
                )
            replace_path(paths.config, chosen)
        else:
            chosen = previous_config
        paths.config.parent.mkdir(parents=True, exist_ok=True)
        replace_path(stage_config, paths.config)
        sync_dir(paths.config.parent)
        return chosen
    if (
        not paths.config.exists()
        and previous_config is not None
        and previous_config.exists()
    ):
        replace_path(previous_config, paths.config)
        sync_dir(paths.config.parent)
    return previous_config


def _finish_config(
    paths: Paths,
    marker_path: Path,
    marker: RestoreMarker,
    stage_config: Path | None,
    previous_config: Path | None,
) -> Path | None:
    if (
        stage_config is not None
        and stage_config.is_dir()
        and any(stage_config.iterdir())
        and paths.config.exists()
        and previous_config is None
    ):
        previous_config = _unique(
            paths.config.with_name(f"{paths.config.name}.bak-{_stamp()}")
        )
        write_marker(
            marker_path,
            replace(
                marker,
                phase="staged",
                previous_config=str(previous_config),
            ),
        )
    return _swap_config(paths, stage_config, previous_config, _stamp())


def _restored(
    marker_path: Path,
    bundle: Path,
    resumed: bool,
    manifest: Manifest,
    started: float,
    previous_data: Path | None,
    previous_config: Path | None,
    counts: dict[str, int] | None = None,
) -> RestoreOutcome:
    return RestoreOutcome(
        status="restored",
        marker=marker_path,
        bundle=bundle,
        resumed=resumed,
        files=len(manifest.files),
        counts=counts or manifest.counts,
        revision=manifest.schema_revision,
        previous_data=previous_data,
        previous_config=previous_config,
        duration_ms=round((time.monotonic() - started) * 1000),
    )


def _refused(
    marker_path: Path,
    bundle: Path,
    resumed: bool,
    error: RestoreRefused,
) -> RestoreOutcome:
    fields = error.fields or {}
    return RestoreOutcome(
        status="refused",
        marker=marker_path,
        bundle=bundle,
        resumed=resumed,
        reason=fields.get("reason", error.message),
        revision=fields.get("revision"),
        current=fields.get("current"),
    )


def _log_refused(log: EventLogger, error: RestoreRefused) -> None:
    fields = error.fields or {}
    log.warning(
        "restore.refused",
        revision=fields.get("revision", "none"),
        current=fields.get("current", "none"),
        reason=fields.get("reason", error.message),
    )
