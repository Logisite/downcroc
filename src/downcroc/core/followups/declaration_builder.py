from __future__ import annotations

from pathlib import Path

from downcroc.core.followups.declaration import parse_shared
from downcroc.core.followups.log import FollowUpLog
from downcroc.core.followups.payload import (
    PayloadDocument,
    parse_payload_document,
)
from downcroc.core.followups.planner import Planner
from downcroc.core.followups.snapshot import ParentDeclaration
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.domain.batches import Batch, BatchKind, BatchState
from downcroc.domain.campaign import FollowUpOverride
from downcroc.domain.errors import (
    BatchInvalid,
    FollowUpInvalid,
    FollowUpOverrideUnknown,
    FollowUpParentInvalid,
    FollowUpPayloadExtra,
    FollowUpPayloadGap,
)
from downcroc.domain.followups import (
    DeclarationKind,
    DeclarationState,
    FollowUpDeclaration,
)
from downcroc.domain.jobs import Job
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore


class DeclarationBuilder:
    def __init__(
        self,
        planner: Planner,
        content: ContentStore,
        log: EventLogger,
        limits: IntakeLimits,
    ) -> None:
        self._planner = planner
        self._content = content
        self._events = FollowUpLog(log)
        self._limits = limits

    def parent_jobs(self, parent: Batch) -> list[Job]:
        if parent.kind is not BatchKind.CAMPAIGN:
            raise FollowUpParentInvalid(
                "follow-ups are declared on a campaign batch",
                hint="use the original campaign batch",
            )
        if parent.state is BatchState.CANCELLED:
            raise FollowUpParentInvalid(
                "the campaign batch is cancelled",
                hint="submit a new campaign",
            )
        if parent.source_kind == "csv":
            raise FollowUpParentInvalid(
                "CSV parents do not support declarations",
                hint="submit the campaign as JSON first",
            )
        initial = self._planner.initial_jobs(parent.id, 10_000)
        if not initial:
            raise FollowUpParentInvalid(
                "the campaign has no sent recipients",
                hint="declare the follow-up after at least one message is sent",
            )
        return initial

    def shared(
        self,
        parent: Batch,
        key: str,
        raw: bytes,
        initial: list[Job],
        existing: FollowUpDeclaration | None,
    ) -> FollowUpDeclaration:
        try:
            shared = parse_shared(raw, step_key=key, limits=self._limits)
        except BatchInvalid as error:
            raise _invalid(error) from error
        self._check_overrides(shared.overrides, initial)
        return self._declaration(
            parent,
            key,
            existing,
            kind=DeclarationKind.SHARED,
            after_days=shared.after_days,
            when=shared.when,
            subject=shared.subject,
            text=shared.text,
            html=shared.html,
            require_approval=shared.require_approval,
            overrides=shared.overrides,
            content_ref=None,
            content_hash=None,
        )

    def payload(
        self,
        parent: Batch,
        key: str,
        raw: bytes,
        path: str,
        initial: list[Job],
        existing: FollowUpDeclaration | None,
        dry_run: bool,
    ) -> FollowUpDeclaration:
        try:
            payload = parse_payload_document(
                raw,
                name=key,
                source_dir=Path(path).expanduser().parent,
                limits=self._limits,
                require_schedule=True,
            )
        except BatchInvalid as error:
            raise _invalid(error) from error
        if payload.schedule is None:
            raise FollowUpInvalid(
                "a payload declaration needs a followup block",
                hint="add followup.after_days and followup.when",
            )
        self._events.payload_ignored(parent.id, key, payload.ignored)
        self._check_payload(payload, initial)
        content_ref = existing.content_ref if existing else None
        content_hash = existing.content_hash if existing else None
        if not dry_run:
            stored = self._content.put_followup_payload(parent.id, key, raw)
            content_ref, content_hash = stored.path, stored.hash
        return self._declaration(
            parent,
            key,
            existing,
            kind=DeclarationKind.PAYLOAD,
            after_days=payload.schedule.after_days,
            when=payload.schedule.when,
            subject=None,
            text=None,
            html=None,
            require_approval=payload.schedule.require_approval,
            overrides={},
            content_ref=content_ref,
            content_hash=content_hash,
        )

    def snapshot_keys(self, snapshot: ParentDeclaration) -> set[str]:
        return {step.key for step in snapshot.followups}

    def _declaration(
        self,
        parent: Batch,
        key: str,
        existing: FollowUpDeclaration | None,
        **fields,
    ) -> FollowUpDeclaration:
        now = utc_now()
        return FollowUpDeclaration(
            id=existing.id if existing else new_id("fup"),
            batch_id=parent.id,
            step_key=key,
            state=DeclarationState.ACTIVE,
            version=existing.version if existing else 1,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            **fields,
        )

    def _check_overrides(
        self, overrides: dict[str, FollowUpOverride], initial: list[Job]
    ) -> None:
        known = {job.source_key for job in initial if job.source_key is not None}
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise FollowUpOverrideUnknown(
                "an override names a recipient that is not in the parent",
                hint="use a message key from the parent batch",
                details=[
                    {"code": "followup_override_unknown", "key": item}
                    for item in unknown
                ],
            )

    def _check_payload(self, payload: PayloadDocument, initial: list[Job]) -> None:
        parents = [(job.source_key, job.recipient) for job in initial]
        gaps = payload.gaps(parents)
        if gaps:
            raise FollowUpPayloadGap(
                "the payload has no message for some parent recipients",
                hint="add one message per parent recipient",
                details=[
                    {"code": "followup_payload_gap", "key": item} for item in gaps
                ],
            )
        extras = payload.extras(parents)
        if extras:
            raise FollowUpPayloadExtra(
                "the payload names recipients that are not in the parent",
                hint="remove the extra messages or declare a new campaign",
                details=[
                    {"code": "followup_payload_extra", "key": item} for item in extras
                ],
            )


def _invalid(error: BatchInvalid) -> FollowUpInvalid:
    return FollowUpInvalid(
        error.message,
        hint=error.hint,
        fields=error.fields,
        details=error.details,
    )
