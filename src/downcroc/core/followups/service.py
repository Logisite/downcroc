from __future__ import annotations

import threading

from downcroc.core.events import EventBus
from downcroc.core.followups import catalog
from downcroc.core.followups.builder import DerivedBuilder
from downcroc.core.followups.declaration_service import DeclarationService
from downcroc.core.followups.immediate import ImmediateRunner
from downcroc.core.followups.log import FollowUpLog
from downcroc.core.followups.planner import Planner
from downcroc.core.followups.planning import PlanningRunner
from downcroc.core.followups.sender import SenderResolver
from downcroc.core.followups.status import StatusReport
from downcroc.core.followups.status_service import StatusService
from downcroc.core.followups.stop import FollowUpStopper
from downcroc.core.inbound import InboundService
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.stats import StatsService
from downcroc.domain.errors import DomainError
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.followup_declarations import (
    FollowUpDeclarationRepo,
)
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class FollowUpService:
    def __init__(
        self,
        settings: Settings,
        paths: Paths,
        batches: BatchRepo,
        jobs: JobRepo,
        accounts: AccountRepo,
        messages: MessageRepo,
        content: ContentStore,
        inbound: InboundService,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
        declarations: FollowUpDeclarationRepo,
        send_attempts: SendAttemptRepo,
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._log = log
        self._declaration_repo = declarations
        self._limits = _limits(settings)
        self._planner = Planner(jobs, messages)
        self._senders = SenderResolver(accounts, send_attempts, log)
        self._snapshots = catalog.SnapshotCache(content, self._limits)
        self._builder = DerivedBuilder(
            settings, accounts, jobs, batches, content, send_attempts, log
        )
        self._events = FollowUpLog(log)
        self._status = StatusService(
            batches, jobs, declarations, self._snapshots, self._planner
        )
        self._declarations = DeclarationService(
            settings,
            batches,
            jobs,
            declarations,
            content,
            self._snapshots,
            self._planner,
            log,
            self._limits,
            self._status,
        )
        self._status.configure(self._declarations.loads_payload)
        self._planning = PlanningRunner(
            settings,
            batches,
            jobs,
            self._planner,
            self._senders,
            self._builder,
            inbound,
            stats,
            bus,
            log,
            self._declarations.loads_payload,
        )
        self._planning.configure(self._snapshots)
        self._status.deferred = self._planning.deferred
        self._stopper = FollowUpStopper(batches, jobs, self._planner, log)
        self._immediate = ImmediateRunner(
            settings,
            paths,
            batches,
            jobs,
            self._planner,
            self._builder,
            inbound,
            stats,
            log,
            self._snapshots,
            self._limits,
        )
        self._lock = threading.RLock()

    def plan_due(self) -> None:
        with self._lock:
            self._planning.run(self._declaration_repo.list_active())

    def reload_limits(self) -> None:
        with self._lock:
            self._limits = _limits(self._settings)
            self._snapshots.set_limits(self._limits)

    def cancel_stopped(self) -> None:
        with self._lock:
            self._stopper.cancel_stopped()

    def declare(
        self,
        parent_id: str,
        step: str,
        *,
        path: str,
        kind: str | None,
        version: int | None,
        dry_run: bool,
    ) -> StatusReport:
        with self._lock:
            try:
                return self._declarations.declare(
                    parent_id,
                    step,
                    path=path,
                    kind=kind,
                    version=version,
                    dry_run=dry_run,
                )
            except DomainError as error:
                self._events.rejected(parent_id, step, error.code, error.message)
                raise

    def remove(
        self,
        parent_id: str,
        step: str,
        *,
        version: int | None,
        dry_run: bool,
    ) -> StatusReport:
        with self._lock:
            try:
                return self._declarations.remove(
                    parent_id, step, version=version, dry_run=dry_run
                )
            except DomainError as error:
                self._events.rejected(parent_id, step, error.code, error.message)
                raise

    def retire(
        self,
        parent_id: str,
        step: str,
        *,
        version: int | None,
        confirm: bool,
        dry_run: bool,
    ) -> StatusReport:
        with self._lock:
            try:
                return self._declarations.retire(
                    parent_id,
                    step,
                    version=version,
                    confirm=confirm,
                    dry_run=dry_run,
                )
            except DomainError as error:
                self._events.rejected(parent_id, step, error.code, error.message)
                raise

    def status(self, parent_id: str) -> StatusReport:
        with self._lock:
            return self._status.report(parent_id)

    def create_from_payload(
        self,
        parent_id: str,
        *,
        path: str,
        template: str | None,
        step: str,
        require_approval: bool,
    ) -> str:
        with self._lock:
            try:
                return self._immediate.create(
                    parent_id,
                    path=path,
                    template=template,
                    step=step,
                    require_approval=require_approval,
                )
            except DomainError as error:
                self._events.rejected(parent_id, step, error.code, error.message)
                raise

    def parent_summaries(self, parent_ids: list[str]) -> dict[str, dict[str, object]]:
        if not parent_ids:
            return {}
        with self._lock:
            return {
                parent_id: self._parent_summary(parent_id) for parent_id in parent_ids
            }

    def _parent_summary(self, parent_id: str) -> dict[str, object]:
        report = self._status.report(parent_id)
        child_ids = [
            step.child_batch_id for step in report.steps if step.child_batch_id
        ]
        activity = self._jobs.last_activity(child_ids)
        step_keys = [step.step for step in report.steps]
        last: dict[str, str] | None = None
        last_at = ""
        pending_steps: list[dict[str, object]] = []
        pending_total = 0
        for step in report.steps:
            if step.child_batch_id:
                at = activity.get(step.child_batch_id)
                if at and at >= last_at:
                    last_at = at
                    last = {"step": step.step, "at": at}
            waiting = _waiting(step)
            if waiting > 0 or step.state in {
                "awaiting_approval",
                "scheduled",
                "pending",
                "sending",
                "parent_not_sent",
                "deferred",
            }:
                pending_steps.append(
                    {"step": step.step, "waiting": waiting, "state": step.state}
                )
                pending_total += waiting
        overall = last_at or None
        return {
            "steps": step_keys,
            "last": last,
            "pending": {"total": pending_total, "steps": pending_steps},
            "last_activity": overall,
        }

    def outlook(self, due_within_days: int | None = None) -> list[dict[str, object]]:
        with self._lock:
            items: list[dict[str, object]] = []
            parents = [
                batch
                for batch in self._batches.list(limit=10_000)
                if batch.parent_batch_id is None
            ]
            for batch in parents:
                report = self._status.report(batch.id)
                if not report.steps:
                    continue
                for step in report.steps:
                    if _skip_outlook(step):
                        continue
                    item = self._outlook_item(batch, step)
                    if _within_due(item, due_within_days):
                        items.append(item)
            items.sort(key=_outlook_sort_key)
            return items

    def _outlook_item(self, batch, step) -> dict[str, object]:
        last_sent = None
        if step.child_batch_id:
            activity = self._jobs.last_activity([step.child_batch_id])
            last_sent = activity.get(step.child_batch_id)
        return {
            "batch_id": batch.id,
            "batch_name": batch.name,
            "step": step.step,
            "state": step.state,
            "kind": step.kind,
            "after_days": step.after_days,
            "when": step.when,
            "child_batch_id": step.child_batch_id,
            "counts": dict(step.counts or {}),
            "next_due_at": step.next_due_at,
            "last_sent_at": last_sent,
        }


def _skip_outlook(step) -> bool:
    if step.state in {
        "done",
        "retired",
        "cancelled_child",
        "skipped",
        "broken",
        "partial",
    }:
        return (
            step.counts.get("awaiting", 0) <= 0
            and step.counts.get("candidates", 0) <= 0
        )
    return False


def _within_due(item: dict[str, object], due_within_days: int | None) -> bool:
    if due_within_days is None:
        return True
    if item["state"] in {"pending", "awaiting_approval", "sending"}:
        return True
    due_at = item.get("next_due_at")
    if not due_at:
        return due_within_days >= 0
    try:
        from datetime import UTC, datetime

        moment = datetime.fromisoformat(str(due_at))
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    delta_days = (moment - datetime.now(UTC)).total_seconds() / 86400
    return delta_days <= due_within_days


def _outlook_sort_key(item: dict[str, object]) -> tuple[int, str, str, str]:
    state = str(item.get("state") or "")
    due_at = str(item.get("next_due_at") or "")
    if state in {"pending", "awaiting_approval", "sending"}:
        rank = 0
        due = ""
    elif due_at:
        rank = 1
        due = due_at
    else:
        rank = 2
        due = "9999"
    return (rank, due, str(item.get("batch_id") or ""), str(item.get("step") or ""))


def _waiting(step) -> int:
    counts = step.counts or {}
    return int(
        counts.get("not_due", 0)
        + counts.get("pending", 0)
        + counts.get("awaiting", 0)
        + (
            counts.get("candidates", 0)
            if step.state in {"pending", "scheduled", "parent_not_sent", "deferred"}
            and step.child_batch_id is None
            else 0
        )
    )


def _limits(settings: Settings) -> IntakeLimits:
    return IntakeLimits(
        max_messages=settings.intake.max_messages,
        max_body_bytes=settings.intake.max_body_bytes,
        max_attachment_bytes=settings.intake.max_attachment_bytes,
    )
