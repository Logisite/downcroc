from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from downcroc.backup.fsops import atomic_write, sync_dir


class MarkerError(Exception):
    pass


@dataclass(frozen=True)
class RestoreMarker:
    bundle: str
    requested_at: str
    stage_data: str | None = None
    stage_config: str | None = None
    previous_data: str | None = None
    previous_config: str | None = None
    phase: str = "requested"


def request_marker(bundle: Path) -> RestoreMarker:
    return RestoreMarker(
        bundle=str(bundle),
        requested_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def read_marker(path: Path) -> RestoreMarker:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MarkerError("restore marker cannot be read") from error
    if not isinstance(document, dict):
        raise MarkerError("restore marker is not an object")
    bundle = document.get("bundle")
    requested_at = document.get("requested_at")
    if not isinstance(bundle, str) or not bundle:
        raise MarkerError("restore marker has no bundle")
    if not isinstance(requested_at, str):
        raise MarkerError("restore marker has no request time")

    def optional(name: str) -> str | None:
        value = document.get(name)
        return value if isinstance(value, str) and value else None

    phase = document.get("phase")
    return RestoreMarker(
        bundle=bundle,
        requested_at=requested_at,
        stage_data=optional("stage_data"),
        stage_config=optional("stage_config"),
        previous_data=optional("previous_data"),
        previous_config=optional("previous_config"),
        phase=phase if isinstance(phase, str) and phase else "requested",
    )


def write_marker(path: Path, marker: RestoreMarker) -> None:
    payload = json.dumps(asdict(marker), indent=2, sort_keys=True) + "\n"
    atomic_write(path, payload.encode("utf-8"))


def remove_marker(path: Path) -> None:
    existed = path.exists()
    path.unlink(missing_ok=True)
    if existed:
        sync_dir(path.parent)
