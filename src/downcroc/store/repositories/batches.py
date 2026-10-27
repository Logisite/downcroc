from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.batches import Batch, BatchKind, BatchState, NewBatch
from downcroc.domain.errors import BatchNotFound
from downcroc.store.db.models import BatchRow


def _to_batch(row: BatchRow) -> Batch:
    return Batch(
        id=row.id,
        kind=BatchKind(row.kind),
        parent_batch_id=row.parent_batch_id,
        name=row.name,
        source_ref=row.source_ref,
        source_hash=row.source_hash,
        source_kind=row.source_kind,
        schema_version=row.schema_version,
        campaign_key=row.campaign_key,
        producer_json=row.producer_json,
        template_ref=row.template_ref,
        account_id=row.account_id,
        routing_json=row.routing_json,
        approval=row.approval,
        options_json=row.options_json,
        state=BatchState(row.state),
        sample_job_id=row.sample_job_id,
        samples=tuple(json.loads(row.samples_json or "[]")),
        ignored=tuple(json.loads(row.ignored_json or "[]")),
        warnings=tuple(json.loads(row.warnings_json or "[]")),
        created_at=row.created_at,
        approved_at=row.approved_at,
    )


class BatchRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, batch: NewBatch) -> Batch:
        row = BatchRow(
            id=batch.id,
            kind=batch.kind.value,
            parent_batch_id=batch.parent_batch_id,
            name=batch.name,
            source_ref=batch.source_ref,
            source_hash=batch.source_hash,
            source_kind=batch.source_kind,
            schema_version=batch.schema_version,
            campaign_key=batch.campaign_key,
            producer_json=batch.producer_json,
            template_ref=batch.template_ref,
            account_id=batch.account_id,
            routing_json=batch.routing_json,
            approval=batch.approval,
            options_json=batch.options_json,
            state=batch.state.value,
            sample_job_id=None,
            samples_json=json.dumps(list(batch.samples)),
            ignored_json=json.dumps(list(batch.ignored)),
            warnings_json=json.dumps(list(batch.warnings)),
            created_at=batch.created_at,
            approved_at=None,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return self.get(batch.id)

    def get(self, batch_id: str) -> Batch:
        with self._sessions() as session:
            row = session.get(BatchRow, batch_id)
            if row is None:
                raise BatchNotFound(f"no batch {batch_id}")
            return _to_batch(row)

    def list(
        self,
        *,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Batch]:
        query = select(BatchRow)
        if state is not None:
            query = query.where(BatchRow.state == state)
        query = (
            query.order_by(BatchRow.created_at.desc(), BatchRow.id)
            .offset(offset)
            .limit(limit)
        )
        with self._sessions() as session:
            return [_to_batch(row) for row in session.scalars(query)]

    def count(self, *, state: str | None = None) -> int:
        query = select(func.count()).select_from(BatchRow)
        if state is not None:
            query = query.where(BatchRow.state == state)
        with self._sessions() as session:
            return int(session.scalar(query) or 0)

    def set_state(
        self,
        batch_id: str,
        state: BatchState,
        *,
        approved_at: str | None = None,
    ) -> Batch:
        with self._sessions.begin() as session:
            row = self._row(session, batch_id)
            row.state = state.value
            if approved_at is not None:
                row.approved_at = approved_at
        return self.get(batch_id)

    def set_sample_job(self, batch_id: str, job_id: str) -> Batch:
        with self._sessions.begin() as session:
            row = self._row(session, batch_id)
            row.sample_job_id = job_id
        return self.get(batch_id)

    def _row(self, session: Session, batch_id: str) -> BatchRow:
        row = session.get(BatchRow, batch_id)
        if row is None:
            raise BatchNotFound(f"no batch {batch_id}")
        return row
