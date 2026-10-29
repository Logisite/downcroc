from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import OAuthClientNotFound
from downcroc.domain.transports import (
    AccountTransport,
    OAuthClient,
    TransportHealth,
    TransportKind,
)
from downcroc.store.db.models import AccountTransportRow, OAuthClientRow


def _to_client(row: OAuthClientRow) -> OAuthClient:
    return OAuthClient(
        id=row.id,
        provider_id=row.provider_id,
        label=row.label,
        client_id=row.client_id,
        project_id=row.project_id,
        secret_ref=row.secret_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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


class OAuthClientRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list(self, provider_id: str | None = None) -> list[OAuthClient]:
        with self._sessions() as session:
            query = select(OAuthClientRow).order_by(
                OAuthClientRow.provider_id,
                OAuthClientRow.created_at,
                OAuthClientRow.id,
            )
            if provider_id is not None:
                query = query.where(OAuthClientRow.provider_id == provider_id)
            return [_to_client(row) for row in session.scalars(query)]

    def get(self, client_id: str) -> OAuthClient:
        with self._sessions() as session:
            return _to_client(self._row(session, client_id))

    def find(self, provider_id: str, client_id: str) -> OAuthClient | None:
        with self._sessions() as session:
            row = session.scalar(
                select(OAuthClientRow).where(
                    OAuthClientRow.provider_id == provider_id,
                    OAuthClientRow.client_id == client_id,
                )
            )
            return _to_client(row) if row is not None else None

    def create(self, client: OAuthClient) -> OAuthClient:
        row = OAuthClientRow(
            id=client.id,
            provider_id=client.provider_id,
            label=client.label,
            client_id=client.client_id,
            project_id=client.project_id,
            secret_ref=client.secret_ref,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return client

    def update(self, client_id: str, changes: dict[str, object]) -> OAuthClient:
        with self._sessions.begin() as session:
            row = self._row(session, client_id)
            for key, value in changes.items():
                setattr(row, key, value)
        return self.get(client_id)

    def delete(self, client_id: str) -> OAuthClient:
        with self._sessions.begin() as session:
            row = self._row(session, client_id)
            client = _to_client(row)
            session.delete(row)
        return client

    def dependents(self, client_id: str) -> list[AccountTransport]:
        with self._sessions() as session:
            rows = session.scalars(
                select(AccountTransportRow)
                .where(AccountTransportRow.oauth_client_id == client_id)
                .order_by(AccountTransportRow.account_id, AccountTransportRow.id)
            )
            return [_to_transport(row) for row in rows]

    @staticmethod
    def _row(session: Session, client_id: str) -> OAuthClientRow:
        row = session.get(OAuthClientRow, client_id)
        if row is None:
            raise OAuthClientNotFound(f"no oauth client {client_id}")
        return row
