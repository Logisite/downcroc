from __future__ import annotations

from downcroc.domain.jobs import Job, JobState, NewJob, SenderPolicy
from downcroc.store.db.models import JobRow


def to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        batch_id=row.batch_id,
        account_id=row.account_id,
        sender_policy=SenderPolicy(row.sender_policy),
        recipient=row.recipient,
        recipient_name=row.recipient_name,
        source_kind=row.source_kind,
        source_key=row.source_key,
        source_index=row.source_index,
        step_key=row.step_key,
        parent_job_id=row.parent_job_id,
        thread_root_job_id=row.thread_root_job_id,
        vars_json=row.vars_json,
        subject=row.subject,
        body_ref=row.body_ref,
        state=JobState(row.state),
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        message_id=row.message_id,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        retryable=row.retryable,
        created_at=row.created_at,
        updated_at=row.updated_at,
        sent_at=row.sent_at,
        paused_at=row.paused_at,
        paused_reason=row.paused_reason,
    )


def to_row(job: NewJob) -> JobRow:
    return JobRow(
        id=job.id,
        batch_id=job.batch_id,
        account_id=job.account_id,
        sender_policy=job.sender_policy.value,
        recipient=job.recipient,
        recipient_name=job.recipient_name,
        source_kind=job.source_kind,
        source_key=job.source_key,
        source_index=job.source_index,
        step_key=job.step_key,
        parent_job_id=job.parent_job_id,
        thread_root_job_id=job.thread_root_job_id,
        vars_json=job.vars_json,
        subject=job.subject,
        body_ref=job.body_ref,
        state=job.state.value if hasattr(job.state, "value") else job.state,
        attempts=0,
        next_attempt_at=None,
        lease_owner=None,
        lease_expires_at=None,
        message_id=job.message_id,
        last_error_code=None,
        last_error_message=None,
        retryable=None,
        created_at=job.created_at,
        updated_at=job.created_at,
        sent_at=None,
    )
