from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from downcroc.core.events import EventBus
from downcroc.core.stats import StatsService
from downcroc.domain.batches import BatchState
from downcroc.domain.errors import BatchInvalid, JobNotFailed, JobNotFound
from downcroc.domain.failures import FailedJob
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.fs import restrict_fd
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.failures import FailureRepo
from downcroc.store.repositories.jobs import JobRepo


class FailureLog:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def append(self, failure: FailedJob) -> None:
        entries = [
            entry for entry in self.read() if str(entry.get("job")) != failure.job_id
        ]
        entries.append(
            {
                "job": failure.job_id,
                "batch": failure.batch_id,
                "account": failure.account_id,
                "recipient": failure.recipient,
                "code": failure.code,
                "message": failure.message,
                "retryable": failure.retryable,
                "attempts": failure.attempts,
                "failed_at": failure.failed_at,
            }
        )
        self._write(entries)

    def remove(self, job_id: str) -> bool:
        entries = self.read()
        kept = [entry for entry in entries if str(entry.get("job")) != job_id]
        if len(kept) == len(entries):
            return False
        self._write(kept)
        return True

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f"{self._path.name}.tmp")
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
            0o600,
        )
        restrict_fd(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for entry in entries:
                stream.write(json.dumps(entry, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self._path)

    def read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries


class FailureService:
    def __init__(
        self,
        failures: FailureRepo,
        log_file: FailureLog,
        jobs: JobRepo,
        batches: BatchRepo,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._failures = failures
        self._log_file = log_file
        self._jobs = jobs
        self._batches = batches
        self._stats = stats
        self._bus = bus
        self._log = log

    def record(self, job: Job, account_id: str | None = None) -> FailedJob:
        attribution = account_id or job.account_id
        failure = FailedJob(
            job_id=job.id,
            batch_id=job.batch_id,
            account_id=attribution,
            recipient=job.recipient,
            code=job.last_error_code or "send_failed",
            message=job.last_error_message or "",
            retryable=job.retryable,
            attempts=job.attempts,
            failed_at=utc_now(),
        )
        if self._failures.exists(job.id):
            return failure
        self._log_file.append(failure)
        self._failures.add(failure)
        self._stats.record_failed(job, attribution)
        self._log.warning(
            "job.failed",
            job=job.id,
            code=failure.code,
            attempts=job.attempts,
        )
        self._bus.publish(
            "job.failed",
            {"id": job.id, "batch": job.batch_id, "code": failure.code},
        )
        return failure

    def list(self, limit: int = 100, offset: int = 0) -> list[FailedJob]:
        return self._failures.list(limit, offset)

    def count(self) -> int:
        return self._failures.count()

    def get(self, job_id: str) -> FailedJob:
        return self._failures.get(job_id)

    def retry(self, job_id: str) -> Job:
        failure = self._failures.get(job_id)
        job = self._jobs.get(job_id)
        if job.state is not JobState.FAILED:
            raise JobNotFailed(f"job {job_id} is {job.state.value}, not failed")
        batch = self._batches.get(failure.batch_id)
        if batch.state is BatchState.CANCELLED:
            raise BatchInvalid(f"batch {failure.batch_id} is cancelled")
        self._log_file.remove(job_id)
        retried = self._jobs.reset_for_retry(job_id)
        self._failures.remove(job_id)
        if batch.state is BatchState.DONE:
            self._batches.set_state(batch.id, BatchState.SENDING)
        self._stats.touch_batch(failure.batch_id)
        self._log.info("failure.retried", job=job_id, attempt=failure.attempts)
        self._bus.publish(
            "job.retried",
            {"id": job_id, "batch": failure.batch_id},
        )
        return retried

    def retry_all(self) -> int:
        count = 0
        for failure in self._failures.list(limit=10_000):
            try:
                self.retry(failure.job_id)
            except BatchInvalid, JobNotFailed:
                continue
            count += 1
        return count

    def forget(self, job_id: str) -> dict:
        failure = self._failures.get(job_id)
        self._failures.remove(job_id)
        self._log_file.remove(job_id)
        self._log.info("failure.forgotten", job=job_id, batch=failure.batch_id)
        return {"job_id": job_id, "forgotten": True}

    def purge(
        self,
        *,
        states: list[str] | None,
        older_than_days: int | None,
        dry_run: bool,
    ) -> dict:
        cutoff = (
            None if older_than_days is None else utc_after(-older_than_days * 86_400)
        )
        matched = self._failures.matching(states=states, older_than=cutoff)
        if dry_run:
            return {"failures": len(matched), "dry_run": True}
        removed = self._failures.remove_many([item.job_id for item in matched])
        for item in matched:
            self._log_file.remove(item.job_id)
        self._log.info(
            "failures.purged",
            count=removed,
            states=states,
            older_than_days=older_than_days,
        )
        return {"failures": removed, "dry_run": False}

    def reconcile(self) -> int:
        added = 0
        for entry in self._log_file.read():
            failure = self._entry(entry)
            if failure is None or self._failures.exists(failure.job_id):
                continue
            try:
                job = self._jobs.get(failure.job_id)
            except JobNotFound:
                continue
            if job.state is not JobState.FAILED:
                continue
            if self._failures.add(failure):
                added += 1
        if added:
            self._log.info("failure.reconciled", count=added)
        return added

    @staticmethod
    def _entry(entry: dict[str, Any]) -> FailedJob | None:
        try:
            account = entry.get("account")
            return FailedJob(
                job_id=str(entry["job"]),
                batch_id=str(entry["batch"]),
                account_id=None if account is None else str(account),
                recipient=str(entry["recipient"]),
                code=str(entry["code"]),
                message=str(entry["message"]),
                retryable=(
                    None if entry.get("retryable") is None else bool(entry["retryable"])
                ),
                attempts=int(entry.get("attempts") or 0),
                failed_at=str(entry["failed_at"]),
            )
        except KeyError, TypeError, ValueError:
            return None
