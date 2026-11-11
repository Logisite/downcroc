from __future__ import annotations

import json
from collections.abc import Callable

from downcroc.core.followups import catalog
from downcroc.core.followups.planner import PlannedStep, Planner
from downcroc.core.followups.status import (
    StatusReport,
    StepStatus,
    blocked_counts,
    child_counts,
    derive_state,
)
from downcroc.domain.batches import Batch
from downcroc.domain.errors import DomainError, FollowUpPayloadMissing
from downcroc.domain.followups import (
    DeclarationState,
    FollowUpDeclaration,
)
from downcroc.domain.jobs import Job
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.followup_declarations import (
    FollowUpDeclarationRepo,
)
from downcroc.store.repositories.jobs import JobRepo


class StatusService:
    def __init__(
        self,
        batches: BatchRepo,
        jobs: JobRepo,
        declarations: FollowUpDeclarationRepo,
        snapshots: catalog.SnapshotCache,
        planner: Planner,
        payload_loader: Callable[[FollowUpDeclaration], object] | None = None,
    ) -> None:
        self._batches = batches
        self._jobs = jobs
        self._declarations = declarations
        self._snapshots = snapshots
        self._planner = planner
        self._payload_loader = payload_loader
        self.deferred: set[tuple[str, str]] = set()

    def configure(
        self, payload_loader: Callable[[FollowUpDeclaration], object]
    ) -> None:
        self._payload_loader = payload_loader

    def report(
        self, parent_id: str, *, dry_run: bool = False, changed: bool = False
    ) -> StatusReport:
        parent = self._batches.get(parent_id)
        initial = self._planner.initial_jobs(parent.id, 10_000)
        context = self._planner.context(initial) if initial else None
        snapshot = self._snapshots.get(parent)
        automatic = catalog.snapshot_steps(snapshot)
        declarations = self._declarations.list_for_batch(parent.id)
        children = self._children(parent.id)
        rows: list[StepStatus] = []
        earlier: list[PlannedStep] = []
        for planned in automatic:
            child = next(
                (
                    batch
                    for batch in children
                    if _options(batch).get("step") == planned.step.key
                    and not _options(batch).get("declaration")
                ),
                None,
            )
            rows.append(
                self._row(
                    parent,
                    snapshot,
                    planned,
                    None,
                    child,
                    earlier,
                    initial,
                    context,
                    None,
                )
            )
            earlier.append(planned)
        for declaration in declarations:
            planned, detail = self._declared_step(declaration)
            child = next(
                (
                    batch
                    for batch in children
                    if _options(batch).get("declaration") == declaration.id
                ),
                None,
            )
            if planned is None:
                planned = PlannedStep(step=declaration.step(), overrides={})
            rows.append(
                self._row(
                    parent,
                    snapshot,
                    planned,
                    declaration,
                    child,
                    earlier,
                    initial,
                    context,
                    detail,
                )
            )
            if declaration.state is DeclarationState.ACTIVE and detail is None:
                earlier.append(planned)
        return StatusReport(
            batch_id=parent.id,
            steps=tuple(rows),
            dry_run=dry_run,
            changed=changed,
        )

    def _declared_step(
        self, declaration: FollowUpDeclaration
    ) -> tuple[PlannedStep | None, str | None]:
        try:
            payload = (
                self._payload_loader(declaration)
                if declaration.content_ref is not None
                else None
            )
        except FollowUpPayloadMissing:
            return None, "payload_missing"
        except DomainError:
            return None, "payload_invalid"
        return (
            PlannedStep(
                step=declaration.step(),
                overrides=declaration.overrides,
                payload=payload,
                declaration=declaration,
            ),
            None,
        )

    def _row(
        self,
        parent: Batch,
        snapshot,
        planned: PlannedStep,
        declaration: FollowUpDeclaration | None,
        child: Batch | None,
        earlier: list[PlannedStep],
        initial: list[Job],
        context,
        detail: str | None,
    ) -> StepStatus:
        state = declaration.state if declaration else None
        evaluation = None
        counts: dict[str, int]
        if child is not None:
            counts = child_counts(self._jobs.counts(child.id))
        elif state is DeclarationState.RETIRED or detail is not None:
            counts = _empty_counts(len(initial))
        elif context is not None:
            try:
                evaluation = self._planner.plan_step(
                    snapshot, planned, tuple(earlier), initial, context
                )
                counts = blocked_counts(evaluation)
            except DomainError:
                detail = "payload_invalid"
                counts = _empty_counts(len(initial))
        else:
            counts = _empty_counts(0)
        derived = (
            "broken"
            if detail is not None
            and child is None
            and state is not DeclarationState.RETIRED
            else derive_state(
                declaration_state=state,
                child_state=child.state if child is not None else None,
                counts=counts,
                evaluation=evaluation,
                deferred=(parent.id, planned.step.key) in self.deferred,
                parent_sent=bool(initial),
            )
        )
        return StepStatus(
            step=planned.step.key,
            kind=declaration.kind.value if declaration else "automatic",
            state=derived,
            after_days=planned.step.after_days,
            when=planned.step.when,
            require_approval=planned.step.require_approval,
            version=declaration.version if declaration else None,
            child_batch_id=child.id if child is not None else None,
            counts=counts,
            detail=detail,
        )

    def _children(self, parent_id: str) -> list[Batch]:
        return [
            batch
            for batch in self._batches.list(limit=10_000)
            if batch.parent_batch_id == parent_id
        ]


def _options(batch: Batch) -> dict[str, object]:
    try:
        loaded = json.loads(batch.options_json or "{}")
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _empty_counts(candidates: int) -> dict[str, int]:
    return {
        "candidates": candidates,
        "not_due": 0,
        "replied": 0,
        "bounced": 0,
        "suppressed": 0,
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "cancelled": 0,
        "awaiting": 0,
    }
