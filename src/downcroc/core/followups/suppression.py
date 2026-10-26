from __future__ import annotations

from downcroc.core.followups.model import Skip
from downcroc.core.stats import StatsService
from downcroc.domain.errors import JobNotFound
from downcroc.store.repositories.jobs import JobRepo


def record_suppressed(
    stats: StatsService,
    jobs: JobRepo,
    batch_id: str,
    skipped: tuple[Skip, ...],
) -> None:
    counts: dict[str, int] = {}
    for item in skipped:
        if item.reason != "suppressed":
            continue
        try:
            job = jobs.get(item.job_id)
        except JobNotFound:
            continue
        counts[job.account_id] = counts.get(job.account_id, 0) + 1
    for account_id, count in counts.items():
        stats.record_suppressed(batch_id, account_id, count)
