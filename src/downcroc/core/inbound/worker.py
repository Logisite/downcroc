from __future__ import annotations

import queue

from downcroc.core.events import EventBus
from downcroc.core.inbound.signals import (
    FOLDER,
    STOP,
    CursorJob,
    HistoryJob,
    IngestJob,
    WatcherEvent,
    WatcherState,
)
from downcroc.core.stats import StatsService
from downcroc.domain.errors import AccountNotFound
from downcroc.domain.messages import IncomingMessage, PreparedAttachment
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.config.schema import InboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import IngestResult, MessageRepo


class QueueWorker:
    def __init__(
        self,
        queue_: queue.Queue[object],
        accounts: AccountRepo,
        messages: MessageRepo,
        content: ContentStore,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
        settings: InboundSettings,
        initialized_at: str,
    ) -> None:
        self._queue = queue_
        self._accounts = accounts
        self._messages = messages
        self._content = content
        self._stats = stats
        self._bus = bus
        self._log = log
        self._settings = settings
        self._initialized_at = initialized_at

    def run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is STOP:
                    return
                if isinstance(item, IngestJob):
                    self._handle_ingest(item)
                elif isinstance(item, CursorJob):
                    self._handle_cursor(item)
                elif isinstance(item, HistoryJob):
                    self._handle_history(item)
                elif isinstance(item, WatcherState):
                    self._handle_state(item)
                elif isinstance(item, WatcherEvent):
                    self._bus.publish(item.event, item.data)
            except Exception as error:  # noqa: BLE001
                if isinstance(item, (IngestJob, CursorJob, HistoryJob)):
                    item.error = error
                self._log.error(
                    "inbound.worker_failed",
                    error=str(error),
                    kind=type(item).__name__,
                )
            finally:
                if isinstance(item, (IngestJob, CursorJob, HistoryJob)):
                    item.done.set()
                self._queue.task_done()

    def _handle_ingest(self, job: IngestJob) -> None:
        incoming = job.incoming
        if self._before_initialization(incoming.date):
            self._log.info(
                "message.skipped_before_init",
                account=job.account_id,
                date=incoming.date,
                initialized_at=self._initialized_at,
            )
            return
        existing = self._messages.find_existing(
            job.account_id,
            FOLDER,
            incoming.uidvalidity,
            incoming.uid,
            incoming.message_id,
            incoming.provider_id,
        )
        if existing is not None:
            if incoming.uidvalidity > 0:
                self._messages.advance_cursor(
                    job.account_id,
                    incoming.uidvalidity,
                    incoming.uid,
                    utc_now(),
                )
            job.result = existing
            return
        prepared: list[PreparedAttachment] = []
        message_id = new_id("msg")
        for index, attachment in enumerate(incoming.attachments, start=1):
            stored = self._content.put_attachment(
                job.account_id,
                message_id,
                index,
                attachment.filename,
                attachment.payload,
            )
            prepared.append(
                PreparedAttachment(
                    id=new_id("att"),
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=stored.size,
                    path=stored.path,
                    hash=stored.hash,
                    inline=attachment.inline,
                    content_id=attachment.content_id,
                )
            )
        result = self._messages.ingest(
            job.account_id,
            FOLDER,
            incoming,
            tuple(prepared),
            message_id=message_id,
        )
        job.result = result
        self._stats.record_inbound(
            job.account_id,
            confirmed=result.confirmed,
            is_dsn=incoming.is_dsn,
            attributed=result.job_id is not None,
            batch_id=result.batch_id,
        )
        self._log.info(
            "message.ingested",
            message_id=result.message_id,
            uid=incoming.uid,
            thread=result.thread_id,
            account=job.account_id,
        )
        self._log_attribution(incoming, result)
        self._bus.publish(
            "message.ingested",
            {
                "message_id": result.message_id,
                "uid": incoming.uid,
                "thread": result.thread_id,
                "account": job.account_id,
            },
        )
        for attachment in prepared:
            self._log.info(
                "attachment.stored",
                filename=attachment.filename,
                bytes=attachment.size,
                sha256=attachment.hash[:12],
                account=job.account_id,
                message_id=result.message_id,
            )
            self._bus.publish(
                "attachment.stored",
                {
                    "filename": attachment.filename,
                    "bytes": attachment.size,
                    "sha256": attachment.hash[:12],
                    "account": job.account_id,
                    "message_id": result.message_id,
                },
            )

    def _before_initialization(self, date: str) -> bool:
        if not self._settings.ingest_since_init or not self._initialized_at:
            return False
        try:
            started = parse_utc(self._initialized_at).replace(microsecond=0)
            return parse_utc(date) < started
        except ValueError:
            return False

    def _log_attribution(
        self,
        incoming: IncomingMessage,
        result: IngestResult,
    ) -> None:
        kind = "bounce" if incoming.is_dsn else "reply"
        if result.reply_state == "none" and result.unattributed_reason is None:
            kind = "message"
        self._log.info(
            "message.classified",
            message_id=result.message_id,
            kind=kind,
            confidence=result.reply_state,
            headers=_headers(incoming, result.method),
        )
        self._log.info(
            "thread.linked",
            message_id=result.message_id,
            thread=result.thread_id,
            method=result.method,
        )
        if incoming.is_dsn:
            self._log.info(
                "dsn.parsed",
                message_id=result.message_id,
                job=result.job_id,
                status=incoming.dsn_status,
                code=incoming.dsn_code,
            )
        elif result.confirmed or result.reply_state == "probable":
            self._log.info(
                "reply.attributed",
                message_id=result.message_id,
                batch=result.batch_id,
                job=result.root_job_id,
                confirmed=result.confirmed,
            )
        if result.unattributed_reason and not incoming.is_dsn:
            self._log.info(
                "reply.unattributed",
                message_id=result.message_id,
                reason=result.unattributed_reason,
            )
        if result.suppression_added:
            self._log.info(
                "suppression.added",
                address=incoming.from_address,
                reason="confirmed_reply",
                account=result.suppression_account_id,
                message_id=result.message_id,
            )

    def _handle_cursor(self, job: CursorJob) -> None:
        if job.reset:
            self._accounts.reset_cursor(job.account_id, job.uidvalidity)
        else:
            self._accounts.set_baseline(
                job.account_id,
                job.uidvalidity,
                job.last_uid,
                utc_now(),
            )

    def _handle_history(self, job: HistoryJob) -> None:
        self._accounts.set_history_cursor(
            job.account_id,
            job.history_id,
            job.synced_at,
        )

    def _handle_state(self, state: WatcherState) -> None:
        if state.ok:
            self._accounts.watcher_succeeded(state.account_id, utc_now())
            self._bus.publish(
                "watcher.started",
                {
                    "account": state.account_id,
                    "host": state.host,
                    "uidvalidity": state.uidvalidity,
                    "source": state.source,
                    "mode": state.mode,
                },
            )
            return
        self._accounts.watcher_failed(state.account_id, state.reason)
        if state.reason == "gmail_api_disabled":
            self._bus.publish(
                "gmail.api_disabled",
                {
                    "account": state.account_id,
                    "project_id": state.project_id,
                },
            )
        if state.needs_reauth:
            try:
                self._accounts.mark_needs_reauth(state.account_id, state.reason)
            except AccountNotFound:
                return
            self._bus.publish(
                "account.needs_reauth",
                {"id": state.account_id, "reason": state.reason},
            )
            self._log.warning(
                "account.needs_reauth",
                account=state.account_id,
                reason=state.reason,
            )
        self._bus.publish(
            "watcher.stopped",
            {
                "account": state.account_id,
                "reason": state.reason,
                "retry_in_s": state.retry_in_s,
            },
        )


def _headers(incoming: IncomingMessage, method: str) -> list[str]:
    names: list[str] = []
    if incoming.in_reply_to:
        names.append("in-reply-to")
    if incoming.references:
        names.append("references")
    if incoming.is_dsn:
        names.append("delivery-status")
    if method == "subject":
        names.append("subject")
    return names
