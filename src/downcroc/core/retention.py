from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from downcroc.core.maintenance import MAINTENANCE
from downcroc.runtime.clock import utc_after
from downcroc.runtime.config.schema import RetentionSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.activity import ActivityRepo, day_key, hour_key
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo


@dataclass(frozen=True)
class RetentionResult:
    tables: dict[str, int]
    bytes: int


class RetentionService:
    def __init__(
        self,
        settings: RetentionSettings,
        jobs: JobRepo,
        messages: MessageRepo,
        activity: ActivityRepo,
        content: ContentStore,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._jobs = jobs
        self._messages = messages
        self._activity = activity
        self._content = content
        self._log = log
        self._lock = threading.Lock()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.prune)
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "retention.failed",
                    error=error.__class__.__name__,
                )
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._settings.check_s,
                )
                return
            except TimeoutError:
                continue

    def prune(self) -> RetentionResult:
        if not self._lock.acquire(blocking=False):
            return RetentionResult(tables={}, bytes=0)
        try:
            with MAINTENANCE:
                return self._prune_locked()
        finally:
            self._lock.release()

    def _prune_locked(self) -> RetentionResult:
        now = datetime.now(UTC)
        tables: dict[str, int] = {}
        total_bytes = 0
        jobs, job_bytes = self._prune_jobs()
        tables["jobs"] = jobs
        total_bytes += job_bytes
        messages, message_bytes = self._prune_mail()
        tables["messages"] = messages
        total_bytes += message_bytes
        hourly = self._activity.prune_hourly(
            hour_key(now.astimezone() - timedelta(days=self._settings.hourly_days))
        )
        tables["activity_hourly"] = hourly
        daily = self._activity.prune_daily(
            day_key(now.astimezone() - timedelta(days=self._settings.daily_days))
        )
        tables["activity_daily"] = daily
        sizes = {"jobs": job_bytes, "messages": message_bytes}
        for table, count in tables.items():
            if count:
                self._log.info(
                    "retention.pruned",
                    table=table,
                    count=count,
                    bytes=sizes.get(table, 0),
                )
        return RetentionResult(tables=tables, bytes=total_bytes)

    def _prune_jobs(self) -> tuple[int, int]:
        cutoff = utc_after(-self._settings.jobs_days * 86_400)
        chosen = self._jobs.prunable(cutoff, self._settings.jobs_max)
        if not chosen:
            return 0, 0
        paths = [job.body_ref for job in chosen]
        removed_bytes = sum(self._content.discard(path) for path in paths)
        removed = self._jobs.delete_many([job.id for job in chosen])
        return removed, removed_bytes

    def _prune_mail(self) -> tuple[int, int]:
        cutoff = utc_after(-self._settings.mail_days * 86_400)
        chosen = self._messages.prunable_mail(cutoff)
        if not chosen:
            return 0, 0
        removed_bytes = sum(item.bytes for item in chosen)
        for item in chosen:
            for path in item.attachment_paths:
                self._content.discard(path)
        removed = self._messages.delete_mail([item.message_id for item in chosen])
        return removed, removed_bytes
