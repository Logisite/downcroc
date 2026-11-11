from __future__ import annotations

import hashlib
import time
from dataclasses import replace

from downcroc.core.accounts import AccountEligibility
from downcroc.core.batches import planning, samples, snapshot
from downcroc.core.batches.builder import JobBuilder
from downcroc.core.batches.source import CampaignReader
from downcroc.core.batches.views import (
    BatchDetail,
    Preview,
    PreviewFollowUp,
    PreviewMessage,
)
from downcroc.core.capacity import CapacityService
from downcroc.core.events import EventBus
from downcroc.core.inputs import routing
from downcroc.core.inputs.override import fixed_account
from downcroc.core.inputs.routing import RoutingPlan
from downcroc.core.outbound import OutboundService
from downcroc.core.policy import PolicyResolver
from downcroc.core.stats import StatsService
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.campaign import Campaign
from downcroc.domain.errors import (
    AccountUnavailable,
    BatchInvalid,
    BatchNotAwaitingApproval,
    BatchStateConflict,
    SampleAlreadySent,
)
from downcroc.domain.jobs import JobState
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo


class BatchesService:
    def __init__(
        self,
        settings: Settings,
        paths: Paths,
        batches: BatchRepo,
        jobs: JobRepo,
        accounts: AccountRepo,
        messages: MessageRepo,
        content: ContentStore,
        outbound: OutboundService,
        stats: StatsService,
        policy: PolicyResolver,
        bus: EventBus,
        log: EventLogger,
        capacity: CapacityService,
        eligibility: AccountEligibility,
    ) -> None:
        self._settings = settings
        self._capacity = capacity
        self._batches = batches
        self._jobs = jobs
        self._accounts = accounts
        self._messages = messages
        self._content = content
        self._outbound = outbound
        self._stats = stats
        self._policy = policy
        self._bus = bus
        self._log = log
        self._eligibility = eligibility
        self._reader = CampaignReader(settings, paths, log)
        self._builder = JobBuilder(settings, accounts, jobs, content)

    def submit(
        self,
        path: str,
        template: str | None,
        account: str | None = None,
        key: str | None = None,
    ) -> BatchDetail:
        started_at = utc_now()
        started = time.monotonic()
        campaign = self._reader.read(path, template)
        if account:
            campaign = fixed_account(campaign, account)
        if key is not None:
            campaign = replace(
                campaign, messages=planning.select_messages(campaign, key)
            )
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        self._log_detected(path, campaign)
        for item in campaign.ignored:
            self._log.info("input.field_ignored", key=item.key, field=item.field)

        payload = snapshot.campaign_bytes(campaign)
        digest = hashlib.sha256(payload).hexdigest()
        existing = self._batches.find_submit(digest, key) if key is not None else None
        if existing is not None:
            self._log.info(
                "batch.reused",
                batch=existing.id,
                key=key,
                jobs=len(self._jobs.list(batch_id=existing.id, limit=10_000)),
            )
            return replace(self.detail(existing.id), reused=True)

        plan = routing.resolve(
            campaign, self._accounts.list(), self._policy, self._eligibility
        )
        batch_id = new_id("bat")
        approval = campaign.options.approval
        job_state = (
            JobState.AWAITING_APPROVAL if approval == "review" else JobState.QUEUED
        )
        built = self._builder.build(campaign, plan.assignments, batch_id, job_state)
        stored = self._content.put_batch_source(batch_id, payload)
        chosen = samples.select(
            batch_id,
            [job.id for job in built],
            self._settings.intake.sample_count,
        )
        batch = self._batches.create(
            planning.new_batch(
                campaign,
                plan,
                batch_id,
                approval,
                stored,
                chosen,
                started_at,
                key,
            )
        )
        self._jobs.create_many(built)
        self._stats.touch_batch(batch.id)

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
        estimate = self._capacity.batch_eta(batch)
        self._bus.publish(
            "dispatch.capacity",
            {
                "batch": batch.id,
                "lanes": estimate["lanes"],
                "messages": estimate["remaining"],
                "sequential": estimate["serial"],
                "spills_window": estimate["spills_window"],
            },
        )
        return self.detail(batch.id)

    def preview(
        self,
        path: str,
        template: str | None,
        key: str | None,
        account: str | None = None,
        everything: bool = False,
    ) -> Preview:
        campaign = self._reader.read(path, template)
        if account:
            campaign = fixed_account(campaign, account)
        plan: RoutingPlan | None = None
        try:
            plan = routing.resolve(
                campaign, self._accounts.list(), self._policy, self._eligibility
            )
        except AccountUnavailable:
            plan = None
        assignments = plan.assignments if plan else {}
        chosen = campaign.messages
        if key is not None:
            chosen = planning.select_messages(campaign, key)
        elif not everything:
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
            total=len(campaign.messages),
            valid=len(campaign.messages),
            sampled=len(chosen),
            sample_limit=self._settings.intake.sample_count,
            routing=planning.routing_view(campaign, plan),
            followups=tuple(
                PreviewFollowUp(
                    key=step.key,
                    after_days=step.after_days,
                    when=step.when,
                    require_approval=step.require_approval,
                )
                for step in campaign.followups
            ),
            duplicates=campaign.duplicates,
            attachments=planning.attachments(campaign),
        )

    def list(
        self, *, state: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Batch]:
        return self._batches.list(state=state, limit=limit, offset=offset)

    def count(self, *, state: str | None = None) -> int:
        return self._batches.count(state=state)

    def counts(self, batch_id: str) -> dict[str, int]:
        batch = self._batches.get(batch_id)
        totals = self._messages.batch_totals(
            batch_id, planning.reply_window(batch.options_json)
        )
        return {
            **self._jobs.counts(batch_id),
            "inbound": totals.inbound,
            "replies": totals.replies,
            "late_replies": totals.late_replies,
            "bounces": totals.bounces,
        }

    def suppression_preview(self, batch_id: str) -> list[dict[str, str]]:
        self._batches.get(batch_id)
        known: dict[str, set[str]] = {}
        found: dict[tuple[str, str], str] = {}
        for job in self._jobs.list(batch_id=batch_id, limit=10_000):
            if job.account_id not in known:
                known[job.account_id] = self._messages.suppressed_addresses(
                    job.account_id
                )
            if job.recipient in known[job.account_id]:
                found[(job.recipient, job.account_id)] = "confirmed_reply"
        return [
            {
                "address": address,
                "account_id": account_id,
                "reason": reason,
            }
            for (address, account_id), reason in sorted(found.items())
        ]

    def detail(self, batch_id: str) -> BatchDetail:
        batch = self._batches.get(batch_id)
        jobs = self._jobs.list(batch_id=batch_id, limit=10_000)
        return BatchDetail(
            batch=batch,
            counts=self.counts(batch_id),
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
        if batch.state in (BatchState.CANCELLED, BatchState.DONE):
            raise BatchStateConflict(
                f"batch {batch_id} is already {batch.state.value}",
                hint="nothing else needs cancelling",
            )
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
        self._stats.touch_batch(batch_id)
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

    def _first_job(self, batch_id: str) -> str:
        jobs = self._jobs.ids_in_states(
            batch_id, (JobState.AWAITING_APPROVAL, JobState.QUEUED)
        )
        if not jobs:
            raise BatchInvalid("the batch has no sendable job")
        return jobs[0]
