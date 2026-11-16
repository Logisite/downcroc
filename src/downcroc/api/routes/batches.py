from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.confirm import require
from downcroc.api.schemas.batches import (
    ApproveRequest,
    BatchDeleteOut,
    BatchDetailOut,
    BatchOut,
    BatchReassignOut,
    BatchReassignRequest,
    BatchSubmit,
    FollowUpRequest,
    PreviewOut,
    SuppressionPreviewOut,
)
from downcroc.api.schemas.holds import AllPauseRequest, PauseRequest, ResumeRequest
from downcroc.core.bootstrap import Services
from downcroc.domain.batches import Batch


def _recent_key(batch: Batch, summary: dict[str, object] | None) -> tuple[str, str]:
    activity = ""
    if summary:
        activity = str(summary.get("last_activity") or "")
    stamp = max(activity, batch.approved_at or "", batch.created_at or "")
    return (stamp, batch.id)


def _stale_key(batch: Batch, summary: dict[str, object] | None) -> tuple[str, str]:
    activity = ""
    if summary:
        activity = str(summary.get("last_activity") or "")
    if not activity:
        return ("", batch.created_at or "", batch.id)
    return (activity, batch.created_at or "", batch.id)


router = APIRouter(prefix="/api/batches", tags=["batches"])


def _services(request: Request) -> Services:
    return request.app.state.services


def _hold(batch) -> dict[str, object]:
    return {
        "id": batch.id,
        "state": batch.state.value,
        "paused_at": batch.paused_at,
        "paused_reason": batch.paused_reason,
    }


@router.post("/pause", response_model=None)
def pause_all(body: AllPauseRequest, request: Request) -> dict[str, object]:
    if not body.all:
        return {"paused": [], "skipped": [], "count": 0}
    return _services(request).holds.pause_batches(body.reason)


@router.post("/resume", response_model=None)
def resume_all(body: AllPauseRequest, request: Request) -> dict[str, object]:
    if not body.all:
        return {"paused": [], "skipped": [], "count": 0}
    return _services(request).holds.resume_batches()


@router.post("/{batch_id}/pause", response_model=None)
def pause_batch(
    batch_id: str, body: PauseRequest, request: Request
) -> dict[str, object]:
    batch, changed = _services(request).holds.pause_batch(batch_id, body.reason)
    return {"batch": _hold(batch), "changed": changed}


@router.post("/{batch_id}/resume", response_model=None)
def resume_batch(
    batch_id: str, body: ResumeRequest, request: Request
) -> dict[str, object]:
    batch, changed = _services(request).holds.resume_batch(batch_id, body.reason)
    return {"batch": _hold(batch), "changed": changed}


@router.post("", response_model=BatchDetailOut, status_code=201)
def submit_batch(
    body: BatchSubmit, request: Request, response: Response
) -> BatchDetailOut:
    detail = _services(request).batches.submit(
        body.path, body.template, body.account, body.key
    )
    if detail.reused:
        response.status_code = 200
    capacity = _services(request).capacity
    return BatchDetailOut.from_detail(
        detail,
        capacity.batch_eta(detail.batch),
        capacity.selection(
            sum(detail.counts.values()),
            account_ids=[detail.batch.account_id] if detail.batch.account_id else None,
            pinned=detail.batch.account_id is not None,
        ),
    )


@router.post("/preview", response_model=PreviewOut)
def preview_batch(
    body: BatchSubmit,
    request: Request,
    key: str | None = None,
    all: bool = False,
) -> PreviewOut:
    preview = _services(request).batches.preview(
        body.path, body.template, key, body.account, all
    )
    capacity = _services(request).capacity
    account_ids = [body.account] if body.account else None
    return PreviewOut.of(
        preview,
        capacity.selection(
            preview.valid,
            account_ids=account_ids,
            pinned=body.account is not None,
        ),
    )


@router.get("", response_model=list[BatchOut])
def list_batches(
    request: Request,
    response: Response,
    state: str | None = None,
    parents: bool = False,
    sort: str = Query(default="recent"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[BatchOut]:
    services = _services(request)
    service = services.batches
    capacity = services.capacity
    if parents:
        batches = [
            batch
            for batch in service.list(state=state, limit=10_000, offset=0)
            if batch.parent_batch_id is None
        ]
        summaries = services.followups.parent_summaries([batch.id for batch in batches])
        if sort == "stale":
            batches.sort(key=lambda batch: _stale_key(batch, summaries.get(batch.id)))
        else:
            batches.sort(key=lambda batch: _recent_key(batch, summaries.get(batch.id)))
        response.headers["X-Total-Count"] = str(len(batches))
        page = batches[offset : offset + limit]
        return [
            BatchOut.of(
                batch,
                service.counts(batch.id),
                capacity.batch_eta(batch),
                summaries.get(batch.id),
            )
            for batch in page
        ]
    response.headers["X-Total-Count"] = str(service.count(state=state))
    return [
        BatchOut.of(batch, service.counts(batch.id), capacity.batch_eta(batch))
        for batch in service.list(state=state, limit=limit, offset=offset)
    ]


@router.get("/{batch_id}", response_model=BatchDetailOut)
def get_batch(batch_id: str, request: Request) -> BatchDetailOut:
    services = _services(request)
    detail = services.batches.detail(batch_id)
    capacity = services.capacity
    return BatchDetailOut.from_detail(
        detail,
        capacity.batch_eta(detail.batch),
        capacity.selection(
            sum(detail.counts.values()),
            account_ids=[detail.batch.account_id] if detail.batch.account_id else None,
            pinned=detail.batch.account_id is not None,
        ),
    )


@router.post("/{batch_id}/approve", response_model=BatchDetailOut)
async def approve_batch(
    batch_id: str, body: ApproveRequest, request: Request
) -> BatchDetailOut:
    services = _services(request)
    if body.mode == "one":
        batch = services.batches.detail(batch_id).batch
        services.holds.ensure_can_send(
            batch_id=batch_id,
            account_id=batch.account_id,
        )
    detail = await services.batches.approve(batch_id, body.mode)
    return BatchDetailOut.from_detail(detail)


@router.post("/{batch_id}/cancel", response_model=BatchDetailOut)
def cancel_batch(batch_id: str, request: Request) -> BatchDetailOut:
    return BatchDetailOut.from_detail(_services(request).batches.cancel(batch_id))


@router.post("/{batch_id}/reassign", response_model=BatchReassignOut)
def reassign_batch(
    batch_id: str,
    body: BatchReassignRequest,
    request: Request,
    confirm: bool = Query(default=False),
) -> BatchReassignOut:
    if not body.dry_run:
        require(confirm or body.confirm)
    result = _services(request).portability.reassign_batch(
        batch_id,
        to_account_id=body.to_account_id,
        states=body.states or None,
        include_failed=body.include_failed,
        force=body.force,
        dry_run=body.dry_run,
    )
    return BatchReassignOut(**result)


@router.delete("/{batch_id}", response_model=BatchDeleteOut)
def delete_batch(
    batch_id: str,
    request: Request,
    confirm: bool = Query(default=False),
    dry_run: bool = False,
) -> BatchDeleteOut:
    if not dry_run:
        require(confirm)
    result = _services(request).portability.delete_batch(batch_id, dry_run=dry_run)
    return BatchDeleteOut(**result)


@router.post("/{batch_id}/followups", response_model=BatchDetailOut, status_code=201)
def create_followup(
    batch_id: str, body: FollowUpRequest, request: Request
) -> BatchDetailOut:
    services = _services(request)
    created = services.followups.create_from_payload(
        batch_id,
        path=body.path,
        template=body.template,
        step=body.step,
        require_approval=body.require_approval,
    )
    return BatchDetailOut.from_detail(services.batches.detail(created))


@router.get(
    "/{batch_id}/suppression-preview",
    response_model=list[SuppressionPreviewOut],
)
def suppression_preview(batch_id: str, request: Request) -> list[SuppressionPreviewOut]:
    entries = _services(request).batches.suppression_preview(batch_id)
    return [SuppressionPreviewOut(**entry) for entry in entries]


@router.get("/{batch_id}/thread", response_model=None)
def batch_thread(
    batch_id: str,
    request: Request,
    recipient: str | None = None,
    all: bool = False,
) -> dict[str, object]:
    services = _services(request)
    detail = services.batches.detail(batch_id)
    batch = detail.batch
    status = services.followups.status(batch_id)
    threads = services.messages.list_threads(batch_id=batch_id, limit=500)
    reply_summary = [_thread_summary(services, thread) for thread in threads]
    reply_summary.sort(key=lambda item: str(item.get("last_seen") or ""), reverse=True)
    shown_threads = reply_summary if all or recipient else reply_summary[:10]
    payload: dict[str, object] = {
        "batch": {
            "id": batch.id,
            "name": batch.name,
            "kind": batch.kind.value,
            "state": batch.state.value,
            "created_at": batch.created_at,
            "counts": detail.counts,
        },
        "steps": [
            {
                "step": step.step,
                "kind": step.kind,
                "state": step.state,
                "after_days": step.after_days,
                "when": step.when,
                "child_batch_id": step.child_batch_id,
                "counts": step.counts,
                "next_due_at": getattr(step, "next_due_at", None),
            }
            for step in status.steps
        ],
        "threads": shown_threads,
        "thread_total": len(reply_summary),
    }
    if recipient:
        payload["recipient"] = _recipient_chain(services, batch_id, recipient)
    return payload


def _thread_summary(services: Services, thread) -> dict[str, object]:
    _, messages = services.messages.get_thread(thread.id)
    last = messages[-1] if messages else None
    states = [message.reply_state for message in messages]
    has_confirmed = "confirmed" in states
    has_probable = "probable" in states
    has_bounce = any(
        message.is_dsn or message.reply_state == "bounced" for message in messages
    )
    return {
        "id": thread.id,
        "subject": thread.subject,
        "message_count": thread.message_count,
        "reply_count": thread.reply_count,
        "first_seen": thread.first_seen,
        "last_seen": thread.last_seen,
        "last_reply_state": last.reply_state if last else None,
        "has_confirmed": has_confirmed,
        "has_probable": has_probable,
        "has_bounce": has_bounce,
    }


def _recipient_chain(
    services: Services, batch_id: str, recipient: str
) -> dict[str, object] | None:
    jobs = services.jobs.list(batch_id=batch_id, limit=10_000)
    root = next(
        (
            job
            for job in jobs
            if job.recipient.casefold() == recipient.casefold() and job.step_key is None
        ),
        None,
    )
    if root is None:
        root = next(
            (job for job in jobs if job.recipient.casefold() == recipient.casefold()),
            None,
        )
    if root is None:
        return None
    root_id = root.thread_root_job_id or root.id
    chain = services.jobs.thread_jobs(root_id)
    if not chain:
        chain = [root]
    chain.sort(key=lambda job: (job.created_at or "", job.id))
    thread = services.messages.find_thread_by_root(root.message_id)
    thread_payload = None
    if thread is not None:
        detail_thread, summaries = services.messages.get_thread(thread.id)
        full_messages = [
            _message_out(services.messages.get_message(item.id)) for item in summaries
        ]
        thread_payload = {
            "id": detail_thread.id,
            "subject": detail_thread.subject,
            "message_count": detail_thread.message_count,
            "reply_count": detail_thread.reply_count,
            "messages": full_messages,
        }
    return {
        "recipient": root.recipient,
        "root_job_id": root.id,
        "jobs": [_job_chain_item(job) for job in chain],
        "thread": thread_payload,
    }


def _job_chain_item(job) -> dict[str, object]:
    return {
        "id": job.id,
        "step_key": job.step_key,
        "state": job.state.value if hasattr(job.state, "value") else job.state,
        "subject": job.subject,
        "message_id": job.message_id,
        "created_at": job.created_at,
        "sent_at": job.sent_at,
        "updated_at": job.updated_at,
    }


def _message_out(message) -> dict[str, object]:
    return {
        "id": message.id,
        "subject": message.subject,
        "from_address": message.from_address,
        "from_name": message.from_name,
        "to": list(message.to),
        "date": message.date,
        "reply_state": message.reply_state,
        "is_dsn": message.is_dsn,
        "body_text": message.body_text,
        "body_html": message.body_html,
        "body_truncated": message.body_truncated,
        "thread_id": message.thread_id,
        "job_id": message.job_id,
        "message_id": message.message_id,
        "account_id": message.account_id,
        "folder": message.folder,
        "attachments": [
            {
                "id": item.id,
                "filename": item.filename,
                "size": item.size,
                "content_type": item.content_type,
            }
            for item in message.attachments
        ],
    }
