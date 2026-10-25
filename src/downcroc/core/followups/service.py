from __future__ import annotations

import threading
import time

from downcroc.core.batches.source import CampaignReader
from downcroc.core.events import EventBus
from downcroc.core.followups.builder import DerivedBuilder, DerivedInput
from downcroc.core.followups.model import Candidate, Content, Skip, StepEvaluation
from downcroc.core.followups.planner import Anchor, AnchorResult, Planner
from downcroc.core.followups.snapshot import ParentDeclaration, read_parent
from downcroc.core.followups.stop import FollowUpStopper
from downcroc.core.inbound import InboundService
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.domain.batches import Batch, BatchKind, BatchState
from downcroc.domain.campaign import SCHEMA
from downcroc.domain.errors import BatchInvalid, FollowUpSyncFailed
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo


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
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._accounts = accounts
        self._content = content
        self._limits = IntakeLimits(
            max_messages=settings.intake.max_messages,
            max_body_bytes=settings.intake.max_body_bytes,
            max_attachment_bytes=settings.intake.max_attachment_bytes,
        )
        self._inbound = inbound
        self._bus = bus
        self._log = log
        self._reader = CampaignReader(settings, paths, log)
        self._planner = Planner(jobs, messages)
        self._stopper = FollowUpStopper(batches, jobs, self._planner, log)
        self._builder = DerivedBuilder(settings, accounts, jobs, batches, content)
        self._lock = threading.RLock()
        self._snapshots: dict[str, ParentDeclaration] = {}
        self._planned_once: set[tuple[str, str]] = set()
        self._skipped: set[tuple[str, str, str]] = set()
        self._defer: dict[tuple[str, str], float] = {}

    def plan_due(self) -> None:
        with self._lock:
            sync_cache: dict[str, bool] = {}
            for parent in self._campaigns():
                self._plan_parent(parent, sync_cache)

    def cancel_stopped(self) -> None:
        with self._lock:
            self._stopper.cancel_stopped()

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
            parent = self._batches.get(parent_id)
            if parent.kind is not BatchKind.CAMPAIGN:
                raise BatchInvalid("follow-ups are created from a campaign batch")
            if parent.state is BatchState.CANCELLED:
                raise BatchInvalid("the campaign batch is cancelled")
            declaration = self._declaration(parent)
            initial = self._planner.initial_jobs(parent.id, 10_000)
            if not initial:
                raise BatchInvalid("the campaign has no sent recipients")
            context = self._planner.context(initial)
            first = self._planner.immediate(
                declaration, initial, context, step_key=step
            )
            if not first.anchors:
                self._raise_no_recipients(first)
            self._sync_or_fail(first.anchors)
            context = self._planner.context(initial)
            anchors = self._planner.immediate(
                declaration, initial, context, step_key=step
            )
            if not anchors.anchors:
                self._raise_no_recipients(anchors)
            campaign = self._reader.read(path, template)
            candidates, gaps, extras = self._match_payload(campaign, anchors, step)
            if gaps:
                raise BatchInvalid(
                    "the follow-up payload has no content for some recipients",
                    fields={"path": path},
                    details=[
                        {"code": "missing_content", "field": "recipients", "key": item}
                        for item in gaps
                    ],
                )
            warnings = ()
            if extras:
                warnings = (
                    "follow-up payload messages matched no eligible recipient: "
                    + ", ".join(extras),
                )
            source = DerivedInput(
                parent=parent,
                step_key=step,
                name=f"{parent.name} / {step}",
                candidates=tuple(candidates),
                require_approval=require_approval,
                source_kind=campaign.source_kind,
                schema=campaign.schema if campaign.source_kind == "json" else None,
                template=campaign.template,
                producer={
                    "source_batch": parent.id,
                    "step": step,
                    "payload": path,
                },
                warnings=warnings,
                ignored=campaign.ignored,
            )
            self._log.info(
                "followup.planned",
                batch=parent.id,
                step=step,
                candidates=len(candidates),
                replied=first.replied,
                bounced=first.bounced,
                suppressed=first.suppressed,
                pending=first.pending,
            )
            batch = self._create(source)
            self._log_skip_many(first.skipped)
            return batch.id

    def _plan_parent(self, parent: Batch, sync_cache: dict[str, bool]) -> None:
        declaration = self._declaration(parent)
        if not declaration.followups:
            return
        initial = self._planner.initial_jobs(parent.id, 10_000)
        if not initial:
            return
        context = self._planner.context(initial)
        for step in declaration.followups:
            evaluation = self._planner.plan_step(declaration, step, initial, context)
            self._log_skip_many(evaluation.skipped)
            if not evaluation.candidates:
                self._log_planned_once(parent, evaluation)
                continue
            allowed = []
            for candidate in evaluation.candidates:
                account_id = candidate.parent.account_id
                if account_id not in sync_cache:
                    sync_cache[account_id] = self._sync_account(
                        parent, step.key, account_id
                    )
                if sync_cache[account_id]:
                    allowed.append(candidate)
            if not allowed:
                self._log_planned_once(parent, evaluation)
                continue
            self._log_planned(parent, evaluation, len(allowed))
            source = DerivedInput(
                parent=parent,
                step_key=step.key,
                name=f"{parent.name} / {step.key}",
                candidates=tuple(allowed),
                require_approval=step.require_approval,
                source_kind="json",
                schema=SCHEMA,
                template=None,
                producer={"source_batch": parent.id, "step": step.key},
            )
            batch = self._create(source)
            self._log.info(
                "followup.created",
                batch=batch.id,
                source_batch=parent.id,
                step=step.key,
                jobs=len(allowed),
            )
            self._bus.publish(
                "followup.created",
                {
                    "batch_id": batch.id,
                    "parent_batch_id": parent.id,
                    "step": step.key,
                    "jobs": len(allowed),
                },
            )
            context = self._planner.context(initial)

    def _create(self, source: DerivedInput) -> Batch:
        return self._builder.create(source)

    def _campaigns(self) -> list[Batch]:
        return [
            batch
            for batch in self._batches.list(limit=10_000)
            if batch.kind is BatchKind.CAMPAIGN
            and batch.state is not BatchState.CANCELLED
        ]

    def _declaration(self, batch: Batch) -> ParentDeclaration:
        cached = self._snapshots.get(batch.source_ref)
        if cached is None:
            cached = read_parent(batch, self._content, self._limits)
            self._snapshots[batch.source_ref] = cached
        return cached

    def _sync_account(self, parent: Batch, step: str, account_id: str) -> bool:
        key = (account_id, step)
        now = time.monotonic()
        if self._defer.get(key, 0.0) > now:
            return False
        ok, reason = self._inbound.sync_wait(
            account_id, self._settings.followups.sync_timeout_s
        )
        if ok:
            self._defer.pop(key, None)
            return True
        self._defer[key] = now + self._settings.followups.defer_s
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

    def _sync_or_fail(self, anchors: tuple[Anchor, ...]) -> None:
        failed: list[str] = []
        for account_id in sorted({item.parent.account_id for item in anchors}):
            ok, reason = self._inbound.sync_wait(
                account_id, self._settings.followups.sync_timeout_s
            )
            if not ok:
                failed.append(f"{account_id}:{reason}")
        if failed:
            raise FollowUpSyncFailed(
                "inbound sync failed before creating the follow-up",
                details=[
                    {"code": "sync_failed", "field": "account", "key": item}
                    for item in failed
                ],
            )

    def _match_payload(
        self,
        campaign,
        anchors: AnchorResult,
        step: str,
    ) -> tuple[list[Candidate], list[str], list[str]]:
        by_key = {message.key: message for message in campaign.messages}
        by_email = {
            message.recipient.email.lower(): message for message in campaign.messages
        }
        used: set[str] = set()
        candidates: list[Candidate] = []
        gaps: list[str] = []
        for anchor in anchors.anchors:
            message = None
            key = anchor.parent.source_key
            if key is not None:
                found = by_key.get(key)
                if (
                    found is not None
                    and found.recipient.email.lower() == anchor.parent.recipient.lower()
                ):
                    message = found
            if message is None:
                message = by_email.get(anchor.parent.recipient.lower())
            if message is None:
                gaps.append(anchor.parent.recipient)
                continue
            used.add(message.key)
            candidates.append(
                Candidate(
                    parent=anchor.parent,
                    anchor=anchor.sent,
                    step_key=step,
                    content=Content(
                        subject=message.subject,
                        text=message.text,
                        html=message.html,
                        attachments=message.attachments,
                        source_dir=campaign.source_dir,
                    ),
                    source_kind=campaign.source_kind,
                    source_key=(
                        message.key if campaign.source_kind == "json" else None
                    ),
                    source_index=message.source_index,
                    references=anchor.references,
                )
            )
        extras = [
            message.recipient.email
            for message in campaign.messages
            if message.key not in used
        ]
        return candidates, gaps, extras

    def _raise_no_recipients(self, result: AnchorResult) -> None:
        details = [
            {"code": item.reason, "field": "recipients", "key": item.job_id}
            for item in result.skipped
        ]
        raise BatchInvalid(
            "no eligible recipients for the follow-up",
            details=details or None,
        )

    def _log_planned_once(self, parent: Batch, evaluation: StepEvaluation) -> None:
        key = (parent.id, evaluation.step_key)
        if key in self._planned_once:
            return
        self._planned_once.add(key)
        self._log.info(
            "followup.planned",
            batch=parent.id,
            step=evaluation.step_key,
            candidates=0,
            replied=evaluation.replied,
            bounced=evaluation.bounced,
            suppressed=evaluation.suppressed,
            pending=evaluation.pending,
            not_due=evaluation.not_due,
        )

    def _log_planned(
        self,
        parent: Batch,
        evaluation: StepEvaluation,
        allowed: int,
    ) -> None:
        self._planned_once.add((parent.id, evaluation.step_key))
        self._log.info(
            "followup.planned",
            batch=parent.id,
            step=evaluation.step_key,
            candidates=allowed,
            replied=evaluation.replied,
            bounced=evaluation.bounced,
            suppressed=evaluation.suppressed,
            pending=evaluation.pending,
            not_due=evaluation.not_due,
        )

    def _log_skip_many(self, skipped: tuple[Skip, ...]) -> None:
        for item in skipped:
            self._log_skip(item.job_id, item.step_key, item.reason)

    def _log_skip(self, job_id: str, step: str, reason: str) -> None:
        key = (job_id, step, reason)
        if key in self._skipped:
            return
        self._skipped.add(key)
        self._log.info(
            "followup.skipped",
            job=job_id,
            step=step,
            reason=reason,
        )
