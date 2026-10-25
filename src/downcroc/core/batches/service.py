from __future__ import annotations

import json
import time

from downcroc.core.batches import samples, snapshot
from downcroc.core.batches.builder import JobBuilder
from downcroc.core.batches.source import CampaignReader
from downcroc.core.batches.views import (
    BatchDetail,
    Preview,
    PreviewMessage,
)
from downcroc.core.events import EventBus
from downcroc.core.inputs import routing
from downcroc.core.inputs.routing import RoutingPlan
from downcroc.core.outbound import OutboundService
from downcroc.domain.batches import Batch, BatchKind, BatchState, NewBatch
from downcroc.domain.campaign import Campaign
from downcroc.domain.errors import (
    AccountUnavailable,
    BatchInvalid,
    BatchNotAwaitingApproval,
    SampleAlreadySent,
)
from downcroc.domain.jobs import JobState
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.content import ContentStore, StoredContent
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo


class BatchesService:
    def __init__(
        self,
        settings: Settings,
        paths: Paths,
        batches: BatchRepo,
        jobs: JobRepo,
        accounts: AccountRepo,
        content: ContentStore,
        outbound: OutboundService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._batches = batches
        self._jobs = jobs
        self._accounts = accounts
        self._content = content
        self._outbound = outbound
        self._bus = bus
        self._log = log
        self._reader = CampaignReader(settings, paths, log)
        self._builder = JobBuilder(settings, accounts, jobs, content)

    def submit(self, path: str, template: str | None) -> BatchDetail:
        started_at = utc_now()
        started = time.monotonic()
        campaign = self._reader.read(path, template)
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        self._log_detected(path, campaign)
        for item in campaign.ignored:
            self._log.info("input.field_ignored", key=item.key, field=item.field)

        plan = routing.resolve(campaign, self._accounts.list())
        batch_id = new_id("bat")
        approval = campaign.options.approval
        job_state = (
            JobState.AWAITING_APPROVAL if approval == "review" else JobState.QUEUED
        )
        built = self._builder.build(campaign, plan.assignments, batch_id, job_state)
        stored = self._content.put_batch_source(
            batch_id, snapshot.campaign_bytes(campaign)
        )
        chosen = samples.select(
            batch_id,
            [job.id for job in built],
            self._settings.intake.sample_count,
        )
        batch = self._batches.create(
            self._new_batch(
                campaign,
                plan,
                batch_id,
                approval,
                stored,
                chosen,
                started_at,
            )
        )
        self._jobs.create_many(built)

        self._log.info(
            "input.parsed",
            messages=len(campaign.messages),
            duplicates=campaign.duplicates,
            duration_ms=elapsed_ms,
        )
        self._log.info(
            "routing.resolved",
            batch=batch.id,
            accounts=len(set(plan.assignments.values())),
            messages=len(plan.assignments),
        )
        self._log.info("snapshot.stored", hash=stored.hash, bytes=stored.size)
        self._log.info(
            "batch.created",
            batch=batch.id,
            jobs=len(built),
            followups=len(campaign.followups),
        )
        self._bus.publish(
            "batch.created",
            {
                "batch_id": batch.id,
                "jobs": len(built),
                "source_kind": campaign.source_kind,
                "state": batch.state.value,
            },
        )
        return self.detail(batch.id)

    def preview(self, path: str, template: str | None, key: str | None) -> Preview:
        campaign = self._reader.read(path, template)
        assignments: dict[str, str] = {}
        try:
            assignments = routing.resolve(campaign, self._accounts.list()).assignments
        except AccountUnavailable:
            assignments = {}
        chosen = campaign.messages
        if key is not None:
            chosen = tuple(
                message
                for message in campaign.messages
                if message.key == key or str(message.source_index) == key
            )
            if not chosen:
                raise BatchInvalid(
                    f"no message or row matches {key}",
                    fields={"key": "not found in the source"},
                )
        else:
            chosen = chosen[: self._settings.intake.sample_count]
        return Preview(
            source_kind=campaign.source_kind,
            campaign_key=campaign.key,
            campaign_name=campaign.name,
            routing_mode=campaign.routing.mode,
            messages=tuple(
                PreviewMessage(
                    key=message.key,
                    row=message.source_index if campaign.source_kind == "csv" else None,
                    email=message.recipient.email,
                    name=message.recipient.name,
                    subject=message.subject,
                    text=message.text,
                    html=message.html,
                    attachments=message.attachments,
                    account_id=assignments.get(message.key),
                )
                for message in chosen
            ),
            ignored=tuple(item.field for item in campaign.ignored),
        )

    def list(self, *, state: str | None = None, limit: int = 100) -> list[Batch]:
        return self._batches.list(state=state, limit=limit)

    def counts(self, batch_id: str) -> dict[str, int]:
        return self._jobs.counts(batch_id)

    def detail(self, batch_id: str) -> BatchDetail:
        batch = self._batches.get(batch_id)
        jobs = self._jobs.list(batch_id=batch_id, limit=10_000)
        return BatchDetail(
            batch=batch,
            counts=self._jobs.counts(batch_id),
            jobs=tuple(jobs),
            samples=samples.previews(batch, jobs, self._content),
        )

    async def approve(self, batch_id: str, mode: str) -> BatchDetail:
        batch = self._batches.get(batch_id)
        if mode == "one" and batch.sample_job_id is not None:
            raise SampleAlreadySent("this batch already sent its sample")
        if batch.state is not BatchState.AWAITING_APPROVAL:
            raise BatchNotAwaitingApproval(
                f"batch {batch_id} is {batch.state.value}, not awaiting approval"
            )
        if mode not in {"one", "all"}:
            raise BatchInvalid("approve mode must be one or all")
        if mode == "one":
            chosen = batch.samples[0] if batch.samples else self._first_job(batch_id)
            released = self._jobs.transition_one(
                chosen,
                from_state=JobState.AWAITING_APPROVAL,
                to_state=JobState.QUEUED,
            )
            if released is None:
                raise BatchInvalid("the sample job is not awaiting approval")
            self._batches.set_sample_job(batch_id, chosen)
            await self._outbound.send(chosen)
        else:
            self._jobs.transition_batch(
                batch_id,
                from_states=(JobState.AWAITING_APPROVAL,),
                to_state=JobState.QUEUED,
            )
            now = utc_now()
            self._batches.set_state(batch_id, BatchState.SENDING, approved_at=now)
        self._log.info("batch.approved", batch=batch_id, sample=mode == "one")
        self._bus.publish("batch.approved", {"batch_id": batch_id, "mode": mode})
        return self.detail(batch_id)

    def cancel(self, batch_id: str) -> BatchDetail:
        batch = self._batches.get(batch_id)
        sent = self._jobs.counts(batch_id).get(JobState.SENT.value, 0)
        self._jobs.transition_batch(
            batch_id,
            from_states=(
                JobState.AWAITING_APPROVAL,
                JobState.QUEUED,
                JobState.RETRY_WAIT,
            ),
            to_state=JobState.CANCELLED,
        )
        self._batches.set_state(batch_id, BatchState.CANCELLED)
        self._log.info("batch.cancelled", batch=batch.id, sent_so_far=sent)
        self._bus.publish(
            "batch.cancelled", {"batch_id": batch.id, "sent_so_far": sent}
        )
        return self.detail(batch_id)

    def _log_detected(self, path: str, campaign: Campaign) -> None:
        self._log.info(
            "input.detected",
            path=path,
            format=campaign.source_kind,
            schema=campaign.schema if campaign.source_kind == "json" else None,
        )

    def _new_batch(
        self,
        campaign: Campaign,
        plan: RoutingPlan,
        batch_id: str,
        approval: str,
        stored: StoredContent,
        chosen: tuple[str, ...],
        started_at: str,
    ) -> NewBatch:
        return NewBatch(
            id=batch_id,
            kind=BatchKind.CAMPAIGN,
            parent_batch_id=None,
            name=campaign.name,
            source_ref=stored.path,
            source_hash=stored.hash,
            source_kind=campaign.source_kind,
            schema_version=campaign.schema if campaign.source_kind == "json" else None,
            campaign_key=campaign.key,
            producer_json=json.dumps(campaign.producer, sort_keys=True),
            template_ref=campaign.template,
            account_id=plan.account_id,
            routing_json=plan.as_json(),
            approval=approval,
            options_json=json.dumps(
                {
                    "suppress_replies": campaign.options.suppress_replies,
                    "reply_window_days": campaign.options.reply_window_days,
                    "not_before": campaign.options.not_before,
                    "stop_on": list(campaign.options.stop_on),
                    "allow_duplicates": campaign.options.allow_duplicates,
                },
                sort_keys=True,
            ),
            state=(
                BatchState.AWAITING_APPROVAL
                if approval == "review"
                else BatchState.SENDING
            ),
            samples=chosen,
            ignored=tuple(f"{item.key}:{item.field}" for item in campaign.ignored),
            warnings=(
                (f"{campaign.duplicates} duplicate address(es) collapsed",)
                if campaign.duplicates
                else ()
            ),
            created_at=started_at,
        )

    def _first_job(self, batch_id: str) -> str:
        jobs = self._jobs.ids_in_states(
            batch_id, (JobState.AWAITING_APPROVAL, JobState.QUEUED)
        )
        if not jobs:
            raise BatchInvalid("the batch has no sendable job")
        return jobs[0]
