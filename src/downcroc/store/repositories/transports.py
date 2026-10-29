from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import DomainError
from downcroc.domain.transports import (
    AccountTransport,
    TransportHealth,
    TransportKind,
)
from downcroc.store.db.models import AccountTransportRow, SendAttemptRow


class TransportNotFound(DomainError):
    code = "transport_not_found"
    status = 404


class TransportExists(DomainError):
    code = "transport_exists"
    status = 409


class TransportInvalid(DomainError):
    code = "transport_invalid"
    status = 422


def _to_transport(row: AccountTransportRow) -> AccountTransport:
    return AccountTransport(
        id=row.id,
        account_id=row.account_id,
        provider_id=row.provider_id,
        kind=TransportKind(row.kind),
        credential_ref=row.credential_ref,
        oauth_client_id=row.oauth_client_id,
        enabled=row.enabled,
        priority=row.priority,
        max_concurrency=row.max_concurrency,
        rate_per_min=row.rate_per_min,
        health=TransportHealth(row.health),
        cooldown_until=row.cooldown_until,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        last_success_at=row.last_success_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class TransportRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list_for_account(self, account_id: str) -> list[AccountTransport]:
        with self._sessions() as session:
            rows = session.scalars(
                select(AccountTransportRow)
                .where(AccountTransportRow.account_id == account_id)
                .order_by(
                    AccountTransportRow.priority.desc(),
                    AccountTransportRow.created_at,
                    AccountTransportRow.id,
                )
            )
            return [_to_transport(row) for row in rows]

    def get(self, binding_id: str) -> AccountTransport:
        with self._sessions() as session:
            return _to_transport(self._row(session, binding_id))

    def get_for_account(self, account_id: str, binding_id: str) -> AccountTransport:
        with self._sessions() as session:
            row = self._row(session, binding_id)
            if row.account_id != account_id:
                raise TransportNotFound(f"no transport {binding_id} for {account_id}")
            return _to_transport(row)

    def create(self, binding: AccountTransport) -> AccountTransport:
        row = AccountTransportRow(
            id=binding.id,
            account_id=binding.account_id,
            provider_id=binding.provider_id,
            kind=binding.kind.value,
            credential_ref=binding.credential_ref,
            oauth_client_id=binding.oauth_client_id,
            enabled=binding.enabled,
            priority=binding.priority,
            max_concurrency=binding.max_concurrency,
            rate_per_min=binding.rate_per_min,
            health=binding.health.value,
            cooldown_until=binding.cooldown_until,
            last_error_code=binding.last_error_code,
            last_error_message=binding.last_error_message,
            last_success_at=binding.last_success_at,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )
        with self._sessions.begin() as session:
            exists = session.scalar(
                select(AccountTransportRow.id).where(
                    AccountTransportRow.account_id == binding.account_id,
                    AccountTransportRow.kind == binding.kind.value,
                    AccountTransportRow.provider_id == binding.provider_id,
                )
            )
            if exists is not None:
                raise TransportExists(
                    "the mailbox already has this transport",
                    hint="change the existing binding instead",
                )
            session.add(row)
        return binding

    def update(self, binding_id: str, changes: dict[str, object]) -> AccountTransport:
        if not changes:
            return self.get(binding_id)
        with self._sessions.begin() as session:
            row = self._row(session, binding_id)
            for key, value in changes.items():
                setattr(row, key, value)
            row.updated_at = str(changes.get("updated_at", row.updated_at))
        return self.get(binding_id)

    def delete(self, binding_id: str) -> AccountTransport:
        with self._sessions.begin() as session:
            row = self._row(session, binding_id)
            binding = _to_transport(row)
            session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.binding_id == binding_id)
                .values(binding_id=None)
            )
            session.delete(row)
        return binding

    def record_success(self, binding_id: str, at: str) -> AccountTransport:
        with self._sessions.begin() as session:
            row = self._row(session, binding_id)
            row.health = TransportHealth.READY.value
            row.cooldown_until = None
            row.last_error_code = None
            row.last_error_message = None
            row.last_success_at = at
            row.updated_at = at
        return self.get(binding_id)

    def record_failure(
        self,
        binding_id: str,
        *,
        health: TransportHealth,
        code: str,
        message: str,
        cooldown_until: str | None,
        at: str,
    ) -> AccountTransport:
        with self._sessions.begin() as session:
            row = self._row(session, binding_id)
            row.health = health.value
            row.cooldown_until = cooldown_until
            row.last_error_code = code
            row.last_error_message = message[:500]
            row.updated_at = at
        return self.get(binding_id)

    def count_by_kind(self, account_id: str) -> dict[str, int]:
        counts = {kind.value: 0 for kind in TransportKind}
        for binding in self.list_for_account(account_id):
            counts[binding.kind.value] += 1
        return counts

    @staticmethod
    def _row(session: Session, binding_id: str) -> AccountTransportRow:
        row = session.get(AccountTransportRow, binding_id)
        if row is None:
            raise TransportNotFound(f"no transport {binding_id}")
        return row
