from __future__ import annotations

import queue

from downcroc.core.events import EventBus
from downcroc.core.inbound.signals import (
    FOLDER,
    STOP,
    CursorJob,
    IngestJob,
    WatcherEvent,
    WatcherState,
)
from downcroc.domain.errors import AccountNotFound
from downcroc.domain.messages import PreparedAttachment
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import MessageRepo


class QueueWorker:
    def __init__(
        self,
        queue_: queue.Queue[object],
        accounts: AccountRepo,
        messages: MessageRepo,
        content: ContentStore,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._queue = queue_
        self._accounts = accounts
        self._messages = messages
        self._content = content
        self._bus = bus
        self._log = log

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
                elif isinstance(item, WatcherState):
                    self._handle_state(item)
                elif isinstance(item, WatcherEvent):
                    self._bus.publish(item.event, item.data)
            except Exception as error:  # noqa: BLE001
                if isinstance(item, (IngestJob, CursorJob)):
                    item.error = error
                self._log.error(
                    "inbound.worker_failed",
                    error=str(error),
                    kind=type(item).__name__,
                )
            finally:
                if isinstance(item, (IngestJob, CursorJob)):
                    item.done.set()
                self._queue.task_done()

    def _handle_ingest(self, job: IngestJob) -> None:
        incoming = job.incoming
        existing = self._messages.find_existing(
            job.account_id,
            FOLDER,
            incoming.uidvalidity,
            incoming.uid,
            incoming.message_id,
        )
        if existing is not None:
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
        self._log.info(
            "message.ingested",
            message_id=result.message_id,
            uid=incoming.uid,
            thread=result.thread_id,
            account=job.account_id,
        )
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

    def _handle_state(self, state: WatcherState) -> None:
        if state.ok:
            self._accounts.watcher_succeeded(state.account_id, utc_now())
            self._bus.publish(
                "watcher.started",
                {
                    "account": state.account_id,
                    "host": state.host,
                    "uidvalidity": state.uidvalidity,
                },
            )
            return
        self._accounts.watcher_failed(state.account_id, state.reason)
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
