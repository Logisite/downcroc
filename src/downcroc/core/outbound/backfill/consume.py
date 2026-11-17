from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from downcroc.core.outbound.backfill.api_stage import ApiStage, Outcome
from downcroc.core.outbound.backfill.lanes import PassStats
from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ThreadHole
from downcroc.domain.providers import ProviderSpec
from downcroc.runtime.logging.setup import EventLogger

PROGRESS_STATES = {"resolved", "missing", "waiting", "unresolved"}


class PageTurn:
    """One page of due holes: IMAP sweep hits first, then stage-2 lookups.

    Returns whether the page moved at least one hole, so a page full of
    waiting holes cannot block later pages forever.
    """

    def __init__(self, stage: ApiStage, log: EventLogger, max_concurrency: int) -> None:
        self._stage = stage
        self._log = log
        self._max_concurrency = max_concurrency

    def run(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
        holes: list[ThreadHole],
        sweep_threads: dict[str, set[str]] | None,
        stats: PassStats,
    ) -> bool:
        leftovers = []
        progressed = False
        for hole in holes:
            candidates = (
                sweep_threads.get(hole.message_id)
                if sweep_threads is not None
                else None
            )
            if candidates is not None and len(candidates) == 1:
                outcome = self._stage.write(
                    account,
                    hole,
                    next(iter(candidates)),
                    medium="imap",
                    scope="imap",
                )
                if outcome.state == "resolved":
                    stats.resolved += 1
                    progressed = True
                continue
            if candidates is not None and len(candidates) > 1:
                self._log.info("backfill.ambiguous", attempt=hole.attempt_id)
            leftovers.append(hole)
        for outcome in self._api_outcomes(account, spec, token, leftovers):
            if outcome.state == "resolved":
                stats.resolved += 1
            elif outcome.state == "missing":
                stats.missing += 1
            elif outcome.state == "unresolved":
                stats.unresolved += 1
            elif outcome.state == "waiting":
                stats.waiting += 1
            else:
                stats.errors += 1
            if outcome.state in PROGRESS_STATES:
                progressed = True
        return progressed

    def _api_outcomes(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
        holes: list[ThreadHole],
    ) -> list[Outcome]:
        if not holes:
            return []
        width = min(self._max_concurrency, len(holes))
        if width <= 1:
            return [self._stage.resolve(account, spec, hole, token) for hole in holes]
        with ThreadPoolExecutor(max_workers=width) as pool:
            return list(
                pool.map(
                    lambda hole: self._stage.resolve(account, spec, hole, token),
                    holes,
                )
            )
