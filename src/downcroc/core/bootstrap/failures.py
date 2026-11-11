from __future__ import annotations

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.dispatch import FailureLog, FailureService
from downcroc.store.repositories.failures import FailureRepo


def build_failures(foundation: Foundation) -> FailureService:
    return FailureService(
        FailureRepo(foundation.sessions),
        FailureLog(foundation.paths.data / "failed.jsonl"),
        foundation.jobs,
        foundation.batches,
        foundation.stats,
        foundation.bus,
        foundation.log,
    )
