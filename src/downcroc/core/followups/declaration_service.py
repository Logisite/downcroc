from __future__ import annotations

import json
from pathlib import Path

from downcroc.core.followups import catalog
from downcroc.core.followups.declaration import check_step_key, detect_kind
from downcroc.core.followups.declaration_builder import DeclarationBuilder
from downcroc.core.followups.log import FollowUpLog
from downcroc.core.followups.payload import PayloadDocument, parse_payload_document
from downcroc.core.followups.planner import Planner
from downcroc.core.followups.status import StatusReport, StepStatus
from downcroc.core.followups.status_service import StatusService
from downcroc.core.inputs.detector import read_source
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import (
    ContentCorrupt,
    ContentMissing,
    FollowUpConfirmRequired,
    FollowUpInFlight,
    FollowUpInvalid,
    FollowUpNotFound,
    FollowUpPayloadMissing,
    FollowUpStepExists,
    FollowUpStepUsed,
    FollowUpVersionConflict,
    FollowUpVersionRequired,
)
from downcroc.domain.followups import (
    DeclarationKind,
    DeclarationState,
    FollowUpDeclaration,
)
from downcroc.domain.jobs import JobState
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging import correlation
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.followup_declarations import (
    FollowUpDeclarationRepo,
)
from downcroc.store.repositories.jobs import JobRepo


class DeclarationService:
    def __init__(
        self,
        settings: Settings,
        batches: BatchRepo,
        jobs: JobRepo,
        declarations: FollowUpDeclarationRepo,
        content: ContentStore,
        snapshots: catalog.SnapshotCache,
        planner: Planner,
        log: EventLogger,
        limits: IntakeLimits,
        status: StatusService,
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._declarations = declarations
        self._content = content
        self._snapshots = snapshots
        self._log = log
        self._events = FollowUpLog(log)
        self._limits = limits
        self._status = status
        self._builder = DeclarationBuilder(planner, content, log, limits)

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
        parent = self._batches.get(parent_id)
        initial = self._builder.parent_jobs(parent)
        key = check_step_key(step)
        existing = self._declarations.get(parent.id, key)
        child = self._child(parent.id, key, existing.id if existing else None)
        if existing is not None:
            self._check_update(existing, child, version)
        else:
            self._check_new(parent, key, child)
        raw = read_source(Path(path).expanduser(), self._settings.intake.max_file_bytes)
        selected = DeclarationKind(kind) if kind else detect_kind(raw)
        if selected is DeclarationKind.PAYLOAD:
            declaration = self._builder.payload(
                parent, key, raw, path, initial, existing, dry_run
            )
        else:
            declaration = self._builder.shared(parent, key, raw, initial, existing)
        if not dry_run:
            if existing is None:
                declaration = self._declarations.create(declaration)
            else:
                declaration = self._declarations.update(declaration, version)
            self._log.info(
                "followup.declared",
                batch=parent.id,
                step=declaration.step_key,
                kind=declaration.kind.value,
                after_days=declaration.after_days,
                when=declaration.when,
                require_approval=declaration.require_approval,
                overrides_count=len(declaration.overrides),
                version=declaration.version,
                correlation_id=correlation.current(),
            )
            return self._status.report(parent_id, changed=True)
        return self._dry_run_report(parent_id, declaration)

    def _dry_run_report(
        self, parent_id: str, declaration: FollowUpDeclaration
    ) -> StatusReport:
        report = self._status.report(parent_id, dry_run=True)
        rows = [row for row in report.steps if row.step != declaration.step_key]
        rows.append(
            StepStatus(
                step=declaration.step_key,
                kind=declaration.kind.value,
                state="scheduled",
                after_days=declaration.after_days,
                when=declaration.when,
                require_approval=declaration.require_approval,
                version=declaration.version,
                counts={},
            )
        )
        return StatusReport(
            batch_id=report.batch_id,
            steps=tuple(rows),
            dry_run=True,
            changed=False,
        )

    def remove(
        self,
        parent_id: str,
        step: str,
        *,
        version: int | None,
        dry_run: bool,
    ) -> StatusReport:
        parent = self._batches.get(parent_id)
        declaration = self._required(parent.id, step)
        if declaration.state is DeclarationState.RETIRED:
            raise FollowUpInvalid(
                f"step {step} is retired",
                hint=f"use a new key such as {step}b",
            )
        if version is not None and version != declaration.version:
            raise FollowUpVersionConflict(
                f"step {step} is at version {declaration.version}",
                hint=f"retry with version {declaration.version}",
            )
        child = self._child(parent.id, step, declaration.id)
        counts = self._jobs.counts(child.id) if child is not None else {}
        if counts.get(JobState.SENDING.value, 0):
            raise FollowUpInFlight(
                "a child job is already sending",
                hint="wait for the send to finish, then retire the step",
            )
        sent = counts.get(JobState.SENT.value, 0) + counts.get(
            JobState.SENT_UNCONFIRMED.value, 0
        )
        if sent:
            raise FollowUpInvalid(
                "a sent follow-up cannot be removed",
                hint="retire the step instead; the child history is kept",
            )
        cancelled = 0
        if not dry_run:
            if child is not None:
                cancelled = self._jobs.transition_batch(
                    child.id,
                    from_states=(
                        JobState.AWAITING_APPROVAL,
                        JobState.QUEUED,
                        JobState.RETRY_WAIT,
                    ),
                    to_state=JobState.CANCELLED,
                )
                self._batches.set_state(child.id, BatchState.CANCELLED)
                declaration = self._declarations.set_state(
                    parent.id,
                    step,
                    DeclarationState.RETIRED,
                    expected_version=version,
                )
            else:
                self._declarations.delete(parent.id, step)
            self._log.info(
                "followup.removed",
                batch=parent.id,
                step=step,
                cancelled_jobs=cancelled,
                version=declaration.version,
                correlation_id=correlation.current(),
            )
        return self._status.report(parent_id, dry_run=dry_run, changed=not dry_run)

    def retire(
        self,
        parent_id: str,
        step: str,
        *,
        version: int | None,
        confirm: bool,
        dry_run: bool,
    ) -> StatusReport:
        parent = self._batches.get(parent_id)
        declaration = self._required(parent.id, step)
        child = self._child(parent.id, step, declaration.id)
        counts = self._jobs.counts(child.id) if child is not None else {}
        sent = counts.get(JobState.SENT.value, 0) + counts.get(
            JobState.SENT_UNCONFIRMED.value, 0
        )
        if sent and not confirm and not dry_run:
            raise FollowUpConfirmRequired(
                "retiring a sent step needs confirmation",
                hint="pass --yes or confirm=true",
            )
        if not dry_run and declaration.state is not DeclarationState.RETIRED:
            declaration = self._declarations.set_state(
                parent.id,
                step,
                DeclarationState.RETIRED,
                expected_version=version,
            )
            self._log.info(
                "followup.retired",
                batch=parent.id,
                step=step,
                sent_jobs=sent,
                failed_jobs=counts.get(JobState.FAILED.value, 0),
                version=declaration.version,
                correlation_id=correlation.current(),
            )
        return self._status.report(parent_id, dry_run=dry_run, changed=not dry_run)

    def loads_payload(self, declaration: FollowUpDeclaration) -> PayloadDocument:
        if declaration.content_ref is None or declaration.content_hash is None:
            raise FollowUpPayloadMissing(
                "the payload declaration has no stored content",
                hint="declare the step again",
                fields={"step": declaration.step_key},
            )
        try:
            raw = self._content.read(declaration.content_ref, declaration.content_hash)
        except (ContentMissing, ContentCorrupt) as error:
            raise FollowUpPayloadMissing(
                "the stored follow-up payload cannot be read",
                hint="restore it from a backup or declare the step again",
                fields={"step": declaration.step_key},
            ) from error
        return parse_payload_document(
            raw,
            name=declaration.step_key,
            source_dir=self._content.resolve(declaration.content_ref).parent,
            limits=self._limits,
            require_schedule=True,
        )

    def _check_update(
        self,
        existing: FollowUpDeclaration,
        child: Batch | None,
        version: int | None,
    ) -> None:
        if existing.state is not DeclarationState.ACTIVE:
            raise FollowUpStepUsed(
                f"step {existing.step_key} is {existing.state.value}",
                hint=f"use a new key such as {existing.step_key}b",
            )
        if child is not None:
            raise FollowUpStepUsed(
                f"step {existing.step_key} already has a child batch",
                hint=f"use a new key such as {existing.step_key}b",
            )
        if version is None:
            raise FollowUpVersionRequired(
                "updating a step needs the current version",
                hint=f"retry with version {existing.version}",
            )
        if version != existing.version:
            raise FollowUpVersionConflict(
                f"step {existing.step_key} is at version {existing.version}",
                hint=f"re-read the status and retry with version {existing.version}",
            )

    def _check_new(self, parent: Batch, key: str, child: Batch | None) -> None:
        snapshot = self._snapshots.get(parent)
        if key in self._builder.snapshot_keys(snapshot):
            raise FollowUpStepExists(
                f"step {key} is declared in the campaign",
                hint="choose a new step key",
            )
        if child is not None:
            raise FollowUpStepUsed(
                f"step {key} already has a child batch",
                hint=f"use a new key such as {key}b",
            )

    def _required(self, batch_id: str, step: str) -> FollowUpDeclaration:
        declaration = self._declarations.get(batch_id, step)
        if declaration is None:
            raise FollowUpNotFound(
                f"no retroactive follow-up step {step}",
                hint="run downcroc batch followups status",
            )
        return declaration

    def _child(
        self, parent_id: str, step: str, declaration_id: str | None
    ) -> Batch | None:
        for batch in self._batches.list(limit=10_000):
            if batch.parent_batch_id != parent_id:
                continue
            options = _options(batch)
            if options.get("step") != step:
                continue
            if declaration_id is not None:
                if options.get("declaration") == declaration_id:
                    return batch
            elif not options.get("declaration"):
                return batch
        return None


def _options(batch: Batch) -> dict[str, object]:
    try:
        loaded = json.loads(batch.options_json or "{}")
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
