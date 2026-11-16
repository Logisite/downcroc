"""Config swap helpers for the restore flow.

The staged config directory replaces the live config, and the previous
config is kept beside it under a timestamped backup name. Kept separate
from ``restore.py`` so each module owns one part of the swap.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from downcroc.backup.fsops import sync_dir
from downcroc.backup.pending import RestoreMarker, write_marker
from downcroc.domain.errors import RestoreFailed
from downcroc.runtime.fs import replace as replace_path
from downcroc.runtime.paths import Paths


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def unique(path: Path) -> Path:
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


def swap_config(
    paths: Paths,
    stage_config: Path | None,
    previous_config: Path | None,
    backup_stamp: str,
) -> Path | None:
    if (
        stage_config is not None
        and stage_config.is_dir()
        and any(stage_config.iterdir())
    ):
        if paths.config.exists():
            chosen = previous_config
            if chosen is None or chosen.exists():
                chosen = unique(
                    paths.config.with_name(f"{paths.config.name}.bak-{backup_stamp}")
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


def finish_config(
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
        previous_config = unique(
            paths.config.with_name(f"{paths.config.name}.bak-{stamp()}")
        )
        write_marker(
            marker_path,
            replace(
                marker,
                phase="staged",
                previous_config=str(previous_config),
            ),
        )
    return swap_config(paths, stage_config, previous_config, stamp())
