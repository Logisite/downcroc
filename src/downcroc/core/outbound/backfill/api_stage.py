from __future__ import annotations

import time

from downcroc.core.outbound.backfill.evidence import (
    Outcome,
    SearchFailure,
    Turn,
    age_s,
    backoff_delay,
    deadline,
    duration_ms,
)
from downcroc.core.outbound.backfill.lookups import Lookups
from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ThreadHole
from downcroc.domain.providers import ProviderSpec
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.thread_backfill import ThreadBackfillRepo


class ApiStage:
    """Stage 2: per-hole Gmail API search with the evidence-based settle."""

    def __init__(
        self,
        attempts: ThreadBackfillRepo,
        log: EventLogger,
        *,
        settle_s: float,
        retry_base_s: float,
        retry_max_s: float,
        retry_after_days: int,
        project_id: str | None = None,
    ) -> None:
        self._attempts = attempts
        self._log = log
        self._settle_s = settle_s
        self._retry_base_s = retry_base_s
        self._retry_max_s = retry_max_s
        self._retry_after_days = retry_after_days
        self._lookups = Lookups(log, project_id)

    def resolve(
        self, account: Account, spec: ProviderSpec, hole: ThreadHole, token: str
    ) -> Outcome:
        """One lookup turn. Never raises: failures come back as outcomes."""

        started = time.monotonic()
        search = self._lookups.search(account, spec, hole, token)
        if isinstance(search, SearchFailure):
            return self._failed(account, hole, search, started)
        refs = search.page.messages
        thread_ids = {ref.thread_id for ref in refs if ref.thread_id}
        evidence = Turn(
            sent_results=search.sent_results,
            anywhere_results=search.anywhere_results,
        )
        if len(thread_ids) == 1 and search.page.next_page_token is None:
            return self.write(
                account,
                hole,
                thread_ids.pop(),
                medium="api",
                scope=search.scope,
                started=started,
                evidence=evidence,
            )
        if len(thread_ids) > 1:
            self._log.info(
                "backfill.ambiguous", attempt=hole.attempt_id, scope=search.scope
            )
        provider = self._lookups.provider(account, spec, hole, token)
        evidence = Turn(
            sent_results=search.sent_results,
            anywhere_results=search.anywhere_results,
            provider_result=provider.state,
        )
        if provider.state == "hit" and provider.thread_id:
            return self.write(
                account,
                hole,
                provider.thread_id,
                medium="provider",
                scope="provider",
                started=started,
                evidence=evidence,
            )
        if provider.state == "error":
            return self._defer(
                account,
                hole,
                search.scope,
                started,
                evidence,
                reason="provider_error",
                result="error",
                error=provider.error,
            )
        if len(thread_ids) > 1:
            return self._defer(
                account,
                hole,
                search.scope,
                started,
                evidence,
                reason="ambiguous",
                result="ambiguous",
            )
        return self._absent(account, hole, search.scope, started, evidence)

    def write(
        self,
        account: Account,
        hole: ThreadHole,
        thread_id: str,
        *,
        medium: str,
        scope: str,
        started: float | None = None,
        evidence: Turn | None = None,
    ) -> Outcome:
        """Re-read-before-write: a hole filled concurrently is not clobbered."""

        moment = time.monotonic() if started is None else started
        turn = evidence or Turn()
        if self._attempts.resolve(hole.attempt_id, thread_id, scope=scope):
            self._log.info(
                "backfill.resolved",
                attempt=hole.attempt_id,
                job=hole.job_id,
                account=account.id,
                medium=medium,
                scope=scope,
                thread=thread_id,
                age_s=age_s(hole.started_at),
                duration_ms=duration_ms(moment),
            )
            outcome = Outcome("resolved", scope=scope)
        else:
            outcome = Outcome("skipped", reason="concurrent", scope=scope)
        self._checked(account, hole, outcome, turn, moment)
        return outcome

    def _absent(
        self,
        account: Account,
        hole: ThreadHole,
        scope: str,
        started: float,
        evidence: Turn,
    ) -> Outcome:
        age = age_s(hole.started_at)
        if age >= self._settle_s:
            if self._attempts.mark_missing(hole.attempt_id, scope=scope):
                self._log.info(
                    "backfill.missing",
                    attempt=hole.attempt_id,
                    account=account.id,
                    reason="absent_after_full_search",
                    age_s=age,
                    strikes=hole.check_count + 1,
                    sent_results=evidence.sent_results,
                    anywhere_results=evidence.anywhere_results,
                    provider_result=evidence.provider_result,
                )
            outcome = Outcome("missing", reason="absent_after_full_search", scope=scope)
            self._checked(account, hole, outcome, evidence, started)
            return outcome
        next_check = deadline(hole.started_at, self._settle_s)
        if self._attempts.mark_waiting(
            hole.attempt_id,
            next_check_at=next_check,
            result="absent",
            scope=scope,
        ):
            self._log.info(
                "backfill.retry_scheduled",
                attempt=hole.attempt_id,
                account=account.id,
                next_check_at=next_check,
                reason="absent_settle",
            )
        outcome = Outcome(
            "waiting", reason="absent_settle", scope=scope, next_check_at=next_check
        )
        self._checked(account, hole, outcome, evidence, started)
        return outcome

    def _failed(
        self,
        account: Account,
        hole: ThreadHole,
        failure: SearchFailure,
        started: float,
    ) -> Outcome:
        if failure.auth:
            outcome = Outcome("skipped", reason="auth")
            self._checked(account, hole, outcome, Turn(), started)
            return outcome
        return self._defer(
            account,
            hole,
            None,
            started,
            Turn(),
            reason="transient_error",
            result="error",
            error=failure.code,
        )

    def _defer(
        self,
        account: Account,
        hole: ThreadHole,
        scope: str | None,
        started: float,
        evidence: Turn,
        *,
        reason: str,
        result: str,
        error: str | None = None,
    ) -> Outcome:
        if self._error_window_closed(hole):
            if self._attempts.mark_unresolved(
                hole.attempt_id, scope=scope, error=error
            ):
                self._log.info(
                    "backfill.unresolved",
                    attempt=hole.attempt_id,
                    account=account.id,
                    reason="errors_exhausted",
                    error=error,
                    age_s=age_s(hole.started_at),
                )
            outcome = Outcome("unresolved", reason="errors_exhausted", scope=scope)
            self._checked(account, hole, outcome, evidence, started)
            return outcome
        delay = backoff_delay(hole.check_count, self._retry_base_s, self._retry_max_s)
        next_check = utc_after(delay)
        if self._attempts.mark_waiting(
            hole.attempt_id,
            next_check_at=next_check,
            result=result,
            scope=scope,
            error=error,
        ):
            self._log.info(
                "backfill.retry_scheduled",
                attempt=hole.attempt_id,
                account=account.id,
                delay_s=round(delay, 3),
                next_check_at=next_check,
                reason=reason,
            )
        outcome = Outcome(
            "waiting", reason=reason, scope=scope, next_check_at=next_check
        )
        self._checked(account, hole, outcome, evidence, started)
        return outcome

    def _error_window_closed(self, hole: ThreadHole) -> bool:
        if self._retry_after_days <= 0:
            return True
        if hole.first_miss_at is None:
            return False
        first = parse_utc(hole.first_miss_at)
        elapsed = (parse_utc(utc_now()) - first).total_seconds()
        return elapsed >= self._retry_after_days * 86_400

    def _checked(
        self,
        account: Account,
        hole: ThreadHole,
        outcome: Outcome,
        evidence: Turn,
        started: float,
    ) -> None:
        fields = {
            "attempt": hole.attempt_id,
            "account": account.id,
            "job": hole.job_id,
            "message_id": hole.message_id,
            "decision": outcome.state,
            "reason": outcome.reason,
            "sent_results": evidence.sent_results,
            "anywhere_results": evidence.anywhere_results,
            "provider_result": evidence.provider_result,
            "scope": outcome.scope,
            "age_s": age_s(hole.started_at),
            "next_check_at": outcome.next_check_at,
            "duration_ms": duration_ms(started),
        }
        if outcome.state == "resolved":
            self._log.debug("backfill.hole_checked", **fields)
        else:
            self._log.info("backfill.hole_checked", **fields)
