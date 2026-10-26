from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request

from downcroc.api.schemas.backups import (
    BackupOut,
    BackupRequest,
    RestorePendingOut,
    RestoreRequest,
)
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api", tags=["backup"])


def _services(request: Request) -> Services:
    return request.app.state.services


def _stop_after_response(callback: Callable[[], None]) -> None:
    time.sleep(0.5)
    callback()


@router.post("/backups", response_model=BackupOut)
def create_backup(request: Request, body: BackupRequest) -> BackupOut:
    result = _services(request).backup.create(
        Path(body.path),
        include_logs=body.include_logs,
    )
    return BackupOut.of(result)


@router.post("/restore", response_model=RestorePendingOut)
def request_restore(
    request: Request,
    body: RestoreRequest,
    background: BackgroundTasks,
) -> RestorePendingOut:
    outcome = _services(request).restore.request(Path(body.path))
    background.add_task(
        _stop_after_response,
        request.app.state.request_shutdown,
    )
    return RestorePendingOut.of(outcome)
