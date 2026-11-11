from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from downcroc.core.followups.model import (
    Candidate,
    Content,
    Skip,
    StepEvaluation,
)
from downcroc.core.followups.payload import PayloadDocument, reply_subject
from downcroc.core.followups.snapshot import ParentDeclaration
from downcroc.core.followups.threading import ThreadBroken, build_chain
from downcroc.domain.campaign import FollowUpOverride, FollowUpStep
from downcroc.domain.errors import BatchInvalid
from downcroc.domain.followups import FollowUpDeclaration
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.clock import parse_utc
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.thread_signals import ThreadSignals

PENDING = frozenset(
    {
        JobState.QUEUED,
        JobState.AWAITING_APPROVAL,
        JobState.SENDING,
        JobState.RETRY_WAIT,
    }
)
SENT = frozenset({JobState.SENT, JobState.SENT_UNCONFIRMED})


@dataclass(frozen=True)
class Anchor:
    parent: Job
    sent: Job
    references: tuple[str, ...]


@dataclass(frozen=True)
class AnchorResult:
    anchors: tuple[Anchor, ...]
    skipped: tuple[Skip, ...]
    replied: int = 0
    bounced: int = 0
    suppressed: int = 0
    pending: int = 0
    broken: int = 0


@dataclass(frozen=True)
class PlannedStep:
    step: FollowUpStep
    overrides: dict[str, FollowUpOverride]
    payload: PayloadDocument | None = None
    declaration: FollowUpDeclaration | None = None


class Context:
    def __init__(
        self,
        initial_jobs: list[Job],
        chains: dict[str, list[Job]],
        signals: dict[str, ThreadSignals],
        suppressed: dict[str, set[str]],
    ) -> None:
        self._initial = initial_jobs
        self._chains = chains
        self._signals = signals
        self._suppressed = suppressed

    @property
    def initial(self) -> list[Job]:
        return self._initial

    def chain(self, root_id: str) -> list[Job]:
        return self._chains.get(root_id, [])

    def step_job(self, root_id: str, step_key: str) -> Job | None:
        for job in self.chain(root_id):
            if job.step_key == step_key:
                return job
        return None

    def signals(self, root_id: str) -> ThreadSignals:
        reply = False
        bounce = False
        for job in self.chain(root_id):
            item = self._signals.get(job.message_id)
            if item is None:
                continue
            reply = reply or item.reply
            bounce = bounce or item.bounce
        return ThreadSignals(reply=reply, bounce=bounce)

    def suppressed(self, account_id: str) -> set[str]:
        return self._suppressed.get(account_id, set())

    def latest_sent(self, root_id: str) -> Job | None:
        latest = None
        for job in self.chain(root_id):
            if job.state in SENT and job.sent_at is not None:
                latest = job
        return latest


class Planner:
    def __init__(self, jobs: JobRepo, messages: MessageRepo) -> None:
        self._jobs = jobs
        self._messages = messages

    def initial_jobs(self, batch_id: str, limit: int) -> list[Job]:
        return [
            job
            for job in self._jobs.list(batch_id=batch_id, limit=limit)
            if job.step_key is None and job.state in SENT
        ]

    def context(self, initial_jobs: list[Job]) -> Context:
        root_ids = [job.id for job in initial_jobs]
        chains = self._jobs.thread_jobs_many(root_ids)
        message_ids = [
            job.message_id for root in root_ids for job in chains.get(root, [])
        ]
        signals = self._messages.thread_signals_by_root(message_ids)
        accounts = {job.account_id for job in initial_jobs}
        suppressed = {
            account_id: self._messages.suppressed_addresses(account_id)
            for account_id in accounts
        }
        return Context(initial_jobs, chains, signals, suppressed)

    def plan_step(
        self,
        declaration: ParentDeclaration,
        planned: PlannedStep,
        earlier: tuple[PlannedStep, ...],
        initial_jobs: list[Job],
        context: Context,
    ) -> StepEvaluation:
        step = planned.step
        candidates: list[Candidate] = []
        skipped: list[Skip] = []
        replied = bounced = suppressed = pending = not_due = broken = 0
        for parent in initial_jobs:
            reason = self._stopped_reason(declaration, step.when, parent, context)
            if reason is not None:
                skipped.append(Skip(parent.id, step.key, reason))
                if reason == "replied":
                    replied += 1
                elif reason == "bounced":
                    bounced += 1
                else:
                    suppressed += 1
                continue
            if self._earlier_pending(earlier, parent, context):
                pending += 1
                continue
            existing = context.step_job(parent.id, step.key)
            if existing is not None:
                if existing.state in PENDING:
                    pending += 1
                continue
            override = _override(planned, parent)
            if override is not None and override.skip:
                skipped.append(Skip(parent.id, step.key, "override"))
                continue
            anchor = context.latest_sent(parent.id)
            if anchor is None:
                skipped.append(Skip(parent.id, step.key, "parent_not_sent"))
                continue
            if not _due(anchor, step):
                not_due += 1
                continue
            try:
                chain = build_chain(parent, anchor, context.chain(parent.id))
            except ThreadBroken as error:
                skipped.append(Skip(parent.id, step.key, "thread_broken", error.reason))
                broken += 1
                continue
            content = _content_for(planned, parent, override)
            candidates.append(
                Candidate(
                    parent=parent,
                    anchor=anchor,
                    step_key=step.key,
                    content=content,
                    source_kind="json",
                    source_key=parent.source_key,
                    source_index=parent.source_index,
                    references=chain.references,
                )
            )
        return StepEvaluation(
            step_key=step.key,
            candidates=tuple(candidates),
            skipped=tuple(skipped),
            replied=replied,
            bounced=bounced,
            suppressed=suppressed,
            pending=pending,
            not_due=not_due,
            broken=broken,
        )

    def immediate(
        self,
        declaration: ParentDeclaration,
        initial_jobs: list[Job],
        context: Context,
        *,
        step_key: str,
    ) -> AnchorResult:
        anchors: list[Anchor] = []
        skipped: list[Skip] = []
        replied = bounced = suppressed = pending = broken = 0
        for parent in initial_jobs:
            reason = self._stopped_reason(declaration, "no_reply", parent, context)
            if reason is not None:
                skipped.append(Skip(parent.id, step_key, reason))
                if reason == "replied":
                    replied += 1
                elif reason == "bounced":
                    bounced += 1
                else:
                    suppressed += 1
                continue
            if any(
                job.step_key is not None and job.state in PENDING
                for job in context.chain(parent.id)
            ):
                pending += 1
                skipped.append(Skip(parent.id, step_key, "pending_step"))
                continue
            anchor = context.latest_sent(parent.id)
            if anchor is None:
                skipped.append(Skip(parent.id, step_key, "parent_not_sent"))
                continue
            try:
                chain = build_chain(parent, anchor, context.chain(parent.id))
            except ThreadBroken as error:
                skipped.append(Skip(parent.id, step_key, "thread_broken", error.reason))
                broken += 1
                continue
            anchors.append(
                Anchor(parent=parent, sent=anchor, references=chain.references)
            )
        return AnchorResult(
            anchors=tuple(anchors),
            skipped=tuple(skipped),
            replied=replied,
            bounced=bounced,
            suppressed=suppressed,
            pending=pending,
            broken=broken,
        )

    def _stopped_reason(
        self,
        declaration: ParentDeclaration,
        when: str,
        parent: Job,
        context: Context,
    ) -> str | None:
        signals = context.signals(parent.id)
        if when != "always":
            if "reply" in declaration.options.stop_on and signals.reply:
                return "replied"
            if "bounce" in declaration.options.stop_on and signals.bounce:
                return "bounced"
        if (
            declaration.options.suppress_replies
            and parent.recipient in context.suppressed(parent.account_id)
            and not (when == "always" and signals.reply)
        ):
            return "suppressed"
        return None

    def _earlier_pending(
        self,
        earlier: tuple[PlannedStep, ...],
        parent: Job,
        context: Context,
    ) -> bool:
        for step in earlier:
            override = _override(step, parent)
            if override is not None and override.skip:
                continue
            job = context.step_job(parent.id, step.step.key)
            if job is None:
                return True
            if job.state in PENDING:
                return True
        return False


def _override(planned: PlannedStep, parent: Job) -> FollowUpOverride | None:
    if parent.source_key is None:
        return None
    return planned.overrides.get(parent.source_key)


def _content_for(
    planned: PlannedStep,
    parent: Job,
    override: FollowUpOverride | None,
) -> Content:
    if planned.payload is not None:
        message = planned.payload.message_for(parent.source_key, parent.recipient)
        if message is None:
            raise BatchInvalid(
                "the stored payload has no message for a parent recipient",
                fields={"step": planned.step.key, "recipient": parent.recipient},
            )
        subject = message.subject.strip() or reply_subject(parent.subject)
        return Content(
            subject=subject,
            text=message.text,
            html=message.html,
        )
    return _content(planned.step, parent, override)


def _content(
    step: FollowUpStep,
    parent: Job,
    override: FollowUpOverride | None,
) -> Content:
    subject = step.subject
    text = step.text
    html = step.html
    if override is not None:
        if override.subject is not None:
            subject = override.subject
        if override.text is not None:
            text = override.text
            html = override.html
        elif override.html is not None:
            html = override.html
    if not subject:
        subject = reply_subject(parent.subject)
    if not text.strip() and not (html or "").strip():
        raise BatchInvalid(
            "the follow-up has no content",
            fields={"step": step.key},
        )
    return Content(subject=subject, text=text, html=html)


def _due(anchor: Job, step: FollowUpStep) -> bool:
    if anchor.sent_at is None:
        return False
    local = parse_utc(anchor.sent_at).astimezone()
    due = local + timedelta(days=step.after_days)
    return due <= datetime.now().astimezone()
