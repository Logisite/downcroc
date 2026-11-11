from __future__ import annotations

import re

from downcroc.core.accounts import AccountEligibility
from downcroc.core.outbound.jobs.create import require_batch, require_usable
from downcroc.core.policy import PolicyResolver
from downcroc.core.transports import TransportService
from downcroc.core.transports.seats import SlotPlan
from downcroc.domain.accounts import Account
from downcroc.domain.errors import AccountNeedsReauth, CredentialMissing, InvalidJob
from downcroc.domain.jobs import Job, NewJob
from downcroc.mail.mime.builder import build_message, mint_message_id
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo

ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ManualJobs:
    """Create one ad-hoc job and resolve the mailbox that can carry it."""

    def __init__(
        self,
        accounts: AccountRepo,
        jobs: JobRepo,
        content: ContentStore,
        transports: TransportService,
        policy: PolicyResolver,
        batches: BatchRepo,
        eligibility: AccountEligibility,
    ) -> None:
        self._accounts = accounts
        self._jobs = jobs
        self._content = content
        self._transports = transports
        self._policy = policy
        self._batches = batches
        self._eligibility = eligibility

    def create(
        self,
        *,
        account_id: str,
        recipient: str,
        recipient_name: str | None,
        subject: str,
        text: str,
        html: str | None,
        batch_id: str = "manual",
    ) -> Job:
        account = self._accounts.get(account_id)
        require_usable(account)
        if not self._eligibility.credential_present(account):
            raise CredentialMissing(
                "the send credential is missing from the vault",
                hint="connect the account again",
            )
        recipient = recipient.strip().lower()
        subject = subject.strip()
        fields: dict[str, str] = {}
        if not ADDRESS.fullmatch(recipient):
            fields["recipient"] = "must be an email address"
        if not subject:
            fields["subject"] = "must not be empty"
        if not text.strip() and not (html or "").strip():
            fields["text"] = "a text or html body is required"
        if not batch_id.strip():
            fields["batch_id"] = "must not be empty"
        if fields:
            raise InvalidJob("the job fields are not valid", fields=fields)
        require_batch(self._batches, batch_id)
        job_id = new_id("job")
        message_id = mint_message_id(account.address, self._jobs.message_id_exists)
        payload = build_message(
            from_address=account.address,
            from_name=account.label,
            to_address=recipient,
            to_name=recipient_name,
            subject=subject,
            text=text,
            html=html,
            message_id=message_id,
        )
        stored = self._content.put_job_message(job_id, payload)
        return self._jobs.create(
            NewJob(
                id=job_id,
                batch_id=batch_id,
                account_id=account.id,
                recipient=recipient,
                recipient_name=recipient_name,
                vars_json="{}",
                subject=subject,
                body_ref=stored.path,
                message_id=message_id,
                created_at=utc_now(),
            )
        )

    def sender_for(self, job: Job) -> Account:
        if job.account_id is not None:
            return self._accounts.get(job.account_id)
        plan = self._transports.pick_slots()
        ordered = list(plan.active) + [
            account_id for account_id in plan.queue if account_id not in plan.active_set
        ]
        for account_id in ordered:
            account = self._accounts.get(account_id)
            if self._can_carry(account, plan):
                return account
        for account in self._accounts.list():
            if self._can_carry(account, plan):
                return account
        raise AccountNeedsReauth(
            "no mailbox can carry this job",
            hint="connect an account before sending",
        )

    def _can_carry(self, account: Account, plan: SlotPlan) -> bool:
        if not self._eligibility.sendable(account):
            return False
        return bool(self._transports.allowed_kinds(account, plan))
