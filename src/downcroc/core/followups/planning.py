from __future__ import annotations

import time
import traceback
from collections.abc import Callable

from downcroc.core.events import EventBus
from downcroc.core.followups import catalog
from downcroc.core.followups.builder import DerivedBuilder, DerivedInput
from downcroc.core.followups.log import FollowUpLog
from downcroc.core.followups.planner import PlannedStep, Planner
from downcroc.core.followups.sender import SenderResolver
from downcroc.core.followups.snapshot import ParentDeclaration
from downcroc.core.followups.suppression import record_suppressed
from downcroc.core.inbound import InboundService
from downcroc.core.stats import StatsService
from downcroc.domain.batches import Batch, BatchKind, BatchState
from downcroc.domain.campaign import SCHEMA
from downcroc.domain.errors import (
    DomainError,
    FollowUpSenderUnavailable,
    FollowUpSenderUnresolved,
)
from downcroc.domain.followups import FollowUpDeclaration
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo


class PlanningRunner:
    def __init__(
        self,
        settings: Settings,
        batches: BatchRepo,
        jobs: JobRepo,
        planner: Planner,
        senders: SenderResolver,
        builder: DerivedBuilder,
        inbound: InboundService,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
        payload_loader: Callable[[FollowUpDeclaration], object],
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._planner = planner
        self._senders = senders
        self._builder = builder
        self._inbound = inbound
        self._stats = stats
        self._bus = bus
        self._log = log
        self._events = FollowUpLog(log)
        self._payload_loader = payload_loader
        self._defer: dict[tuple[str, str], float] = {}
        self.deferred: set[tuple[str, str]] = set()
        self._snapshots: catalog.SnapshotCache | None = None

    def configure(self, snapshots: catalog.SnapshotCache) -> None:
        self._snapshots = snapshots

    def run(self, active: dict[str, list[FollowUpDeclaration]]) -> None:
        sync_cache: dict[str, bool] = {}
        for parent in self._campaigns():
            try:
                self._plan_parent(parent, active.get(parent.id, []), sync_cache)
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "followup.parent_failed",
                    batch=parent.id,
                    error=error.__class__.__name__,
                    detail=str(error)[:300],
                    traceback=traceback.format_exc()[-4000:],
                )

    def _campaigns(self) -> list[Batch]:
        return [
            batch
            for batch in self._batches.list(limit=10_000)
            if batch.kind is BatchKind.CAMPAIGN
            and batch.state is not BatchState.CANCELLED
        ]

    def _plan_parent(
        self,
        parent: Batch,
        declarations: list[FollowUpDeclaration],
        sync_cache: dict[str, bool],
    ) -> None:
        snapshot = self._snapshot(parent)
        automatic = catalog.snapshot_steps(snapshot)
        retroactive: list[PlannedStep] = []
        for declaration in declarations:
            try:
                retroactive.extend(
                    catalog.declaration_steps([declaration], self._payload_loader)
                )
            except DomainError as error:
                self._events.rejected(
                    parent.id, declaration.step_key, error.code, error.message
                )
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "followup.step_failed",
                    batch=parent.id,
                    step=declaration.step_key,
                    error=error.__class__.__name__,
                    detail=str(error)[:300],
                    traceback=traceback.format_exc()[-4000:],
                )
                self._events.rejected(
                    parent.id,
                    declaration.step_key,
                    "followup_invalid",
                    str(error),
                )
        steps = catalog.merge_steps(automatic, retroactive)
        if not steps:
            return
        initial = self._planner.initial_jobs(parent.id, 10_000)
        if not initial:
            return
        context = self._planner.context(initial)
        for index, planned in enumerate(steps):
            context = self._plan_step(
                parent,
                snapshot,
                planned,
                tuple(steps[:index]),
                initial,
                context,
                sync_cache,
            )

    def _plan_step(
        self,
        parent: Batch,
        snapshot: ParentDeclaration,
        planned: PlannedStep,
        earlier: tuple[PlannedStep, ...],
        initial: list,
        context,
        sync_cache: dict[str, bool],
    ):
        step_key = planned.step.key
        try:
            evaluation = self._planner.plan_step(
                snapshot, planned, earlier, initial, context
            )
        except DomainError as error:
            self._events.rejected(parent.id, step_key, error.code, error.message)
            return context
        except Exception as error:  # noqa: BLE001
            self._log.error(
                "followup.step_failed",
                batch=parent.id,
                step=step_key,
                error=error.__class__.__name__,
                detail=str(error)[:300],
                traceback=traceback.format_exc()[-4000:],
            )
            self._events.rejected(parent.id, step_key, "followup_invalid", str(error))
            return context
        self._events.thread_breaks(parent.id, step_key, evaluation.skipped)
        self._events.skip_many(evaluation.skipped)
        if not evaluation.candidates:
            self._events.planned_once(parent, evaluation)
            return context
        try:
            for candidate in evaluation.candidates:
                self._senders.resolve(candidate.parent)
        except (FollowUpSenderUnavailable, FollowUpSenderUnresolved) as error:
            self._events.rejected(parent.id, step_key, error.code, error.message)
            return context
        allowed = []
        for candidate in evaluation.candidates:
            account_id = candidate.parent.account_id
            if account_id not in sync_cache:
                sync_cache[account_id] = self._sync_account(
                    parent, step_key, account_id
                )
            if sync_cache[account_id]:
                allowed.append(candidate)
        if not allowed:
            self._events.planned_once(parent, evaluation)
            return context
        self._events.planned(parent, evaluation, len(allowed))
        declaration = planned.declaration
        source = DerivedInput(
            parent=parent,
            step_key=step_key,
            name=f"{parent.name} / {step_key}",
            candidates=tuple(allowed),
            require_approval=planned.step.require_approval,
            source_kind="json",
            schema=SCHEMA,
            template=None,
            producer={
                "source_batch": parent.id,
                "step": step_key,
                "declaration": declaration.id if declaration else None,
            },
            declaration_id=declaration.id if declaration else None,
            kind=declaration.kind.value if declaration else "automatic",
        )
        batch = self._builder.create(source)
        self._stats.touch_batch(batch.id)
        record_suppressed(self._stats, self._jobs, batch.id, evaluation.skipped)
        self._log.info(
            "followup.created",
            batch=batch.id,
            source_batch=parent.id,
            step=step_key,
            jobs=len(allowed),
            kind=source.kind,
        )
        self._bus.publish(
            "followup.created",
            {
                "batch_id": batch.id,
                "parent_batch_id": parent.id,
                "step": step_key,
                "jobs": len(allowed),
            },
        )
        return self._planner.context(initial)

    def _sync_account(self, parent: Batch, step: str, account_id: str | None) -> bool:
        key = (account_id or "", step)
        now = time.monotonic()
        if self._defer.get(key, 0.0) > now:
            return False
        if account_id is None:
            return True
        ok, reason = self._inbound.sync_wait(
            account_id, self._settings.followups.sync_timeout_s
        )
        if ok:
            self._defer.pop(key, None)
            self.deferred.discard((parent.id, step))
            return True
        self._defer[key] = now + self._settings.followups.defer_s
        self.deferred.add((parent.id, step))
        self._log.warning(
            "followup.sync_failed",
            account=account_id,
            step=step,
            reason=reason,
            defer_s=self._settings.followups.defer_s,
        )
        self._log.info(
            "followup.deferred",
            batch=parent.id,
            step=step,
            account=account_id,
            reason="sync_failed",
        )
        return False

    def _snapshot(self, parent: Batch) -> ParentDeclaration:
        if self._snapshots is None:
            raise RuntimeError("planning runner is not configured")
        return self._snapshots.get(parent)
