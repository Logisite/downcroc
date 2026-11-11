from __future__ import annotations

import json
from pathlib import Path

from downcroc.core.batches.source import CampaignReader
from downcroc.core.followups import catalog
from downcroc.core.followups.builder import DerivedBuilder, DerivedInput
from downcroc.core.followups.log import FollowUpLog
from downcroc.core.followups.model import Candidate, Content
from downcroc.core.followups.payload import parse_payload_document, reply_subject
from downcroc.core.followups.planner import Anchor, AnchorResult, Planner
from downcroc.core.followups.suppression import record_suppressed
from downcroc.core.inbound import InboundService
from downcroc.core.inputs.detector import detect, read_source
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.stats import StatsService
from downcroc.domain.batches import Batch, BatchKind, BatchState
from downcroc.domain.campaign import Campaign
from downcroc.domain.errors import BatchInvalid, FollowUpStepUsed, FollowUpSyncFailed
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo


class ImmediateRunner:
    def __init__(
        self,
        settings: Settings,
        paths: Paths,
        batches: BatchRepo,
        jobs: JobRepo,
        planner: Planner,
        builder: DerivedBuilder,
        inbound: InboundService,
        stats: StatsService,
        log: EventLogger,
        snapshots: catalog.SnapshotCache,
        limits: IntakeLimits,
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._planner = planner
        self._builder = builder
        self._inbound = inbound
        self._stats = stats
        self._log = log
        self._reader = CampaignReader(settings, paths, log)
        self._snapshots = snapshots
        self._limits = limits
        self._events = FollowUpLog(log)

    def create(
        self,
        parent_id: str,
        *,
        path: str,
        template: str | None,
        step: str,
        require_approval: bool,
    ) -> str:
        parent = self._batches.get(parent_id)
        if parent.kind is not BatchKind.CAMPAIGN:
            raise BatchInvalid("follow-ups are created from a campaign batch")
        if parent.state is BatchState.CANCELLED:
            raise BatchInvalid("the campaign batch is cancelled")
        if self._child_for_step(parent.id, step) is not None:
            raise FollowUpStepUsed(
                f"step {step} already has a child batch",
                hint=f"use a new key such as {step}b",
            )
        declaration = self._snapshots.get(parent)
        initial = self._planner.initial_jobs(parent.id, 10_000)
        if not initial:
            raise BatchInvalid("the campaign has no sent recipients")
        context = self._planner.context(initial)
        first = self._planner.immediate(declaration, initial, context, step_key=step)
        self._events.thread_breaks(parent.id, step, first.skipped)
        if not first.anchors:
            self._raise_no_recipients(first)
        self._sync_or_fail(first.anchors)
        context = self._planner.context(initial)
        anchors = self._planner.immediate(declaration, initial, context, step_key=step)
        if not anchors.anchors:
            self._raise_no_recipients(anchors)
        campaign = self._read_payload(parent.id, path, template, step)
        candidates, gaps, extras = self._match_payload(campaign, anchors, step)
        if gaps:
            raise BatchInvalid(
                "the follow-up payload has no content for some recipients",
                fields={"path": path},
                hint="add one message per parent recipient or use a shared declaration",
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
            kind="immediate",
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
            broken=first.broken,
        )
        batch = self._builder.create(source)
        self._stats.touch_batch(batch.id)
        record_suppressed(self._stats, self._jobs, batch.id, anchors.skipped)
        self._events.skip_many(first.skipped)
        return batch.id

    def _read_payload(
        self, parent_id: str, path: str, template: str | None, step: str
    ) -> Campaign:
        source = Path(path).expanduser()
        raw = read_source(source, self._settings.intake.max_file_bytes)
        if detect(raw) == "csv":
            return self._reader.read(path, template)
        payload = parse_payload_document(
            raw,
            name=step,
            source_dir=source.parent,
            limits=self._limits,
            require_schedule=False,
            declaration=False,
        )
        self._events.payload_ignored(parent_id, step, payload.ignored)
        return payload.campaign

    def _match_payload(
        self, campaign: Campaign, anchors: AnchorResult, step: str
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
            subject = message.subject.strip() or reply_subject(anchor.parent.subject)
            candidates.append(
                Candidate(
                    parent=anchor.parent,
                    anchor=anchor.sent,
                    step_key=step,
                    content=Content(
                        subject=subject,
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

    def _sync_or_fail(self, anchors: tuple[Anchor, ...]) -> None:
        failed: list[str] = []
        for account_id in sorted({item.parent.account_id for item in anchors}):
            if account_id is None:
                continue
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

    def _raise_no_recipients(self, result: AnchorResult) -> None:
        details = [
            {"code": item.reason, "field": "recipients", "key": item.job_id}
            for item in result.skipped
        ]
        raise BatchInvalid(
            "no eligible recipients for the follow-up",
            details=details or None,
        )

    def _child_for_step(self, parent_id: str, step: str) -> Batch | None:
        for batch in self._batches.list(limit=10_000):
            if batch.parent_batch_id != parent_id:
                continue
            try:
                options = json.loads(batch.options_json or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(options, dict) and options.get("step") == step:
                return batch
        return None
