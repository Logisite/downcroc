from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from downcroc.core.batches import samples, snapshot
from downcroc.core.followups.model import Candidate
from downcroc.core.followups.sender import ResolvedSender, SenderResolver
from downcroc.core.followups.threading import subject_has_re
from downcroc.domain.batches import Batch, BatchKind, BatchState, NewBatch
from downcroc.domain.campaign import (
    SCHEMA,
    Campaign,
    CampaignOptions,
    IgnoredField,
    Message,
    Recipient,
    RoutingPolicy,
)
from downcroc.domain.errors import BatchInvalid, FollowUpThreadBroken
from downcroc.domain.jobs import Job, JobState, NewJob
from downcroc.mail.mime.builder import (
    OutgoingAttachment,
    build_message,
    mint_message_id,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


@dataclass(frozen=True)
class DerivedInput:
    parent: Batch
    step_key: str
    name: str
    candidates: tuple[Candidate, ...]
    require_approval: bool
    source_kind: str
    schema: str | None
    template: str | None
    producer: dict[str, object]
    warnings: tuple[str, ...] = ()
    ignored: tuple[IgnoredField, ...] = ()
    declaration_id: str | None = None
    kind: str = "automatic"


class DerivedBuilder:
    def __init__(
        self,
        settings: Settings,
        accounts: AccountRepo,
        jobs: JobRepo,
        batches: BatchRepo,
        content: ContentStore,
        attempts: SendAttemptRepo,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._jobs = jobs
        self._batches = batches
        self._content = content
        self._log = log
        self._senders = SenderResolver(accounts, attempts, log)

    def create(self, source: DerivedInput) -> Batch:
        if not source.candidates:
            raise BatchInvalid("the follow-up has no eligible recipients")
        batch_id = new_id("bat")
        state = (
            JobState.AWAITING_APPROVAL if source.require_approval else JobState.QUEUED
        )
        built = self._jobs_for(source, batch_id, state)
        campaign = self._campaign(source, batch_id)
        stored = self._content.put_batch_source(
            batch_id, snapshot.campaign_bytes(campaign)
        )
        chosen = samples.select(
            batch_id,
            [job.id for job in built],
            self._settings.intake.sample_count,
        )
        batch = self._batches.create(
            self._new_batch(source, batch_id, stored.path, stored.hash, chosen)
        )
        try:
            self._jobs.create_many(built)
        except Exception:
            self._batches.delete(batch_id)
            raise
        return batch

    def _jobs_for(
        self,
        source: DerivedInput,
        batch_id: str,
        state: JobState,
    ) -> list[NewJob]:
        built: list[NewJob] = []
        for item in source.candidates:
            sender = self._sender(item.parent)
            if not item.references or item.references[-1] != item.anchor.message_id:
                raise FollowUpThreadBroken(
                    "the follow-up chain cannot produce a reply",
                    hint="restore the parent job and its message id",
                    fields={"job": item.parent.id, "step": source.step_key},
                )
            job_id = new_id("job")
            message_id = mint_message_id(sender.address, self._jobs.message_id_exists)
            payload = build_message(
                from_address=sender.address,
                from_name=sender.name,
                to_address=item.parent.recipient,
                to_name=item.parent.recipient_name,
                subject=item.content.subject,
                text=item.content.text,
                html=item.content.html,
                message_id=message_id,
                in_reply_to=item.references[-1] if item.references else None,
                references=item.references,
                attachments=self._attachments(item),
            )
            stored = self._content.put_job_message(job_id, payload)
            self._log.info(
                "thread.linked",
                direction="outbound",
                source="followup",
                batch=batch_id,
                step=source.step_key,
                parent=item.anchor.id,
                child=job_id,
                root=item.parent.id,
                account=sender.account_id,
                in_reply_to=item.references[-1],
                references_count=len(item.references),
                references_head=item.references[0],
                subject_has_re=subject_has_re(item.content.subject),
                message_id=message_id,
            )
            built.append(
                NewJob(
                    id=job_id,
                    batch_id=batch_id,
                    account_id=sender.account_id,
                    sender_policy=sender.policy,
                    recipient=item.parent.recipient.lower(),
                    recipient_name=item.parent.recipient_name,
                    source_kind=source.source_kind,
                    source_key=item.source_key,
                    source_index=item.source_index,
                    step_key=source.step_key,
                    parent_job_id=item.anchor.id,
                    thread_root_job_id=item.parent.id,
                    vars_json=json.dumps(
                        {
                            "key": item.parent.source_key or "",
                            "email": item.parent.recipient,
                            "name": item.parent.recipient_name or "",
                            "step": source.step_key,
                        },
                        sort_keys=True,
                    ),
                    subject=item.content.subject,
                    body_ref=stored.path,
                    message_id=message_id,
                    created_at=utc_now(),
                    state=state,
                )
            )
        return built

    def _sender(self, parent: Job) -> ResolvedSender:
        return self._senders.resolve(parent)

    def _campaign(self, source: DerivedInput, batch_id: str) -> Campaign:
        messages = tuple(
            Message(
                key=item.source_key or f"r{item.source_index}",
                recipient=Recipient(
                    email=item.parent.recipient,
                    name=item.parent.recipient_name,
                ),
                subject=item.content.subject,
                text=item.content.text,
                html=item.content.html,
                reply_to=None,
                attachments=item.content.attachments,
                source_index=item.source_index,
            )
            for item in source.candidates
        )
        options = CampaignOptions(
            suppress_replies=self._parent_options(source.parent).get(
                "suppress_replies", True
            ),
            reply_window_days=self._parent_options(source.parent).get(
                "reply_window_days", 60
            ),
            not_before=None,
            stop_on=tuple(
                self._parent_options(source.parent).get("stop_on", ("reply", "bounce"))
            ),
            allow_duplicates=False,
            approval="review" if source.require_approval else "auto",
        )
        return Campaign(
            schema=SCHEMA,
            key=source.parent.campaign_key or batch_id,
            name=source.name,
            producer=source.producer,
            routing=RoutingPolicy(mode="auto"),
            options=options,
            messages=messages,
            followups=(),
            source_kind=source.source_kind,
            template=source.template,
            ignored=source.ignored,
        )

    def _new_batch(
        self,
        source: DerivedInput,
        batch_id: str,
        source_ref: str,
        source_hash: str,
        chosen: tuple[str, ...],
    ) -> NewBatch:
        options = self._parent_options(source.parent)
        approval = "review" if source.require_approval else "auto"
        assignments = {
            item.parent.recipient: item.parent.account_id for item in source.candidates
        }
        pinned = {value for value in assignments.values() if value is not None}
        batch_account = next(iter(pinned)) if len(pinned) == 1 else None
        counts: dict[str, int] = {}
        for account_id in assignments.values():
            if account_id is None:
                continue
            counts[account_id] = counts.get(account_id, 0) + 1
        routing_json = json.dumps(
            {
                "mode": "inherited",
                "account": None,
                "include": [],
                "exclude": [],
                "assignments": assignments,
                "counts": counts,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return NewBatch(
            id=batch_id,
            kind=BatchKind.FOLLOW_UP,
            parent_batch_id=source.parent.id,
            name=source.name,
            source_ref=source_ref,
            source_hash=source_hash,
            source_kind=source.source_kind,
            schema_version=source.schema,
            campaign_key=source.parent.campaign_key,
            producer_json=json.dumps(source.producer, sort_keys=True),
            template_ref=source.template,
            account_id=batch_account,
            routing_json=routing_json,
            approval=approval,
            options_json=json.dumps(
                {
                    "suppress_replies": options.get("suppress_replies", True),
                    "reply_window_days": options.get("reply_window_days", 60),
                    "not_before": None,
                    "stop_on": list(options.get("stop_on", ("reply", "bounce"))),
                    "allow_duplicates": False,
                    "step": source.step_key,
                    "kind": source.kind,
                    "declaration": source.declaration_id,
                },
                sort_keys=True,
            ),
            state=(
                BatchState.AWAITING_APPROVAL
                if source.require_approval
                else BatchState.SENDING
            ),
            samples=chosen,
            ignored=tuple(f"{item.key}:{item.field}" for item in source.ignored),
            warnings=source.warnings,
            created_at=utc_now(),
        )

    def _parent_options(self, parent: Batch) -> dict[str, object]:
        try:
            loaded = json.loads(parent.options_json or "{}")
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _attachments(self, item: Candidate) -> tuple[OutgoingAttachment, ...]:
        root = Path(item.content.source_dir) if item.content.source_dir else None
        parts: list[OutgoingAttachment] = []
        for name in item.content.attachments:
            path = Path(name)
            if not path.is_absolute() and root is not None:
                path = root / path
            try:
                payload = path.read_bytes()
            except OSError as error:
                raise BatchInvalid(
                    f"cannot read attachment {name}: {error.strerror}",
                    fields={"attachments": name},
                ) from error
            if len(payload) > self._settings.intake.max_attachment_bytes:
                raise BatchInvalid(
                    f"attachment {name} is above the size limit",
                    fields={"attachments": name},
                )
            content_type = (
                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            parts.append(
                OutgoingAttachment(
                    filename=path.name,
                    content_type=content_type,
                    payload=payload,
                )
            )
        return tuple(parts)
