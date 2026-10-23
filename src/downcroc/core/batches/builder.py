from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from downcroc.domain.campaign import Campaign, Message
from downcroc.domain.errors import BatchInvalid
from downcroc.domain.jobs import JobState, NewJob
from downcroc.mail.mime.builder import (
    OutgoingAttachment,
    build_message,
    mint_message_id,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.ids import new_id
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo


class JobBuilder:
    def __init__(
        self,
        settings: Settings,
        accounts: AccountRepo,
        jobs: JobRepo,
        content: ContentStore,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._jobs = jobs
        self._content = content

    def build(
        self,
        campaign: Campaign,
        assignments: dict[str, str],
        batch_id: str,
        state: JobState,
    ) -> list[NewJob]:
        built: list[NewJob] = []
        for message in campaign.messages:
            account_id = assignments.get(message.key)
            if account_id is None:
                raise BatchInvalid(f"no account was assigned to {message.key}")
            account = self._accounts.get(account_id)
            job_id = new_id("job")
            message_id = mint_message_id(account.address, self._jobs.message_id_exists)
            payload = build_message(
                from_address=account.address,
                from_name=account.label,
                to_address=message.recipient.email,
                to_name=message.recipient.name,
                subject=message.subject,
                text=message.text,
                html=message.html,
                message_id=message_id,
                reply_to=message.reply_to,
                attachments=self._attachments(campaign, message),
            )
            stored = self._content.put_job_message(job_id, payload)
            built.append(
                NewJob(
                    id=job_id,
                    batch_id=batch_id,
                    account_id=account.id,
                    recipient=message.recipient.email.lower(),
                    recipient_name=message.recipient.name,
                    source_kind=campaign.source_kind,
                    source_key=message.key if campaign.source_kind == "json" else None,
                    source_index=message.source_index,
                    vars_json=json.dumps(
                        {
                            "key": message.key,
                            "email": message.recipient.email,
                            "name": message.recipient.name,
                        },
                        sort_keys=True,
                    ),
                    subject=message.subject,
                    body_ref=stored.path,
                    message_id=message_id,
                    created_at=utc_now(),
                    state=state,
                    thread_root_job_id=job_id,
                )
            )
        return built

    def _attachments(
        self, campaign: Campaign, message: Message
    ) -> tuple[OutgoingAttachment, ...]:
        root = Path(campaign.source_dir)
        parts: list[OutgoingAttachment] = []
        for name in message.attachments:
            path = Path(name)
            if not path.is_absolute():
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
