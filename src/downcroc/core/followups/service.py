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


def _limits(settings: Settings) -> IntakeLimits:
    return IntakeLimits(
        max_messages=settings.intake.max_messages,
        max_body_bytes=settings.intake.max_body_bytes,
        max_attachment_bytes=settings.intake.max_attachment_bytes,
    )
