from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.policy import POLICY_FIELDS, PolicyOverride
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.store.db.models import PolicyOverrideRow

SERVICE_SCOPE = "service"


def account_scope(account_id: str) -> str:
    return f"account:{account_id}"


class PolicyRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self, scope: str) -> PolicyOverride | None:
        with self._sessions() as session:
            row = session.get(PolicyOverrideRow, scope)
            return _to_override(row) if row is not None else None

    def active(self, scope: str, now: str | None = None) -> PolicyOverride | None:
        override = self.get(scope)
        if override is None:
            return None
        if override.expires_at is not None and parse_utc(
            override.expires_at
        ) <= parse_utc(now or utc_now()):
            return None
        return override

    def set(
        self,
        scope: str,
        override: PolicyOverride,
        *,
        expires_at: str | None = None,
    ) -> PolicyOverride:
        stamp = utc_now()
        values = override.values()
        statement = sqlite_insert(PolicyOverrideRow).values(
            scope=scope,
            expires_at=expires_at,
            created_at=stamp,
            updated_at=stamp,
            **values,
        )
        updates = {
            "expires_at": expires_at,
            "updated_at": stamp,
            **{field: values.get(field) for field in POLICY_FIELDS},
        }
        statement = statement.on_conflict_do_update(
            index_elements=[PolicyOverrideRow.scope],
            set_=updates,
        )
        with self._sessions.begin() as session:
            session.execute(statement)
        return PolicyOverride(**values, expires_at=expires_at)

    def clear(self, scope: str) -> bool:
        with self._sessions.begin() as session:
            result = session.execute(
                delete(PolicyOverrideRow).where(PolicyOverrideRow.scope == scope)
            )
            return bool(result.rowcount)

    def clear_expired(self) -> int:
        now = utc_now()
        with self._sessions.begin() as session:
            rows = session.scalars(select(PolicyOverrideRow)).all()
            expired = [
                row
                for row in rows
                if row.expires_at is not None
                and parse_utc(row.expires_at) <= parse_utc(now)
            ]
            for row in expired:
                session.delete(row)
            return len(expired)


def _to_override(row: PolicyOverrideRow) -> PolicyOverride:
    return PolicyOverride(
        daily_allowance=row.daily_allowance,
        window_start=row.window_start,
        window_end=row.window_end,
        jitter_min=row.jitter_min,
        jitter_max=row.jitter_max,
        max_in_flight=row.max_in_flight,
        enabled=row.enabled,
        expires_at=row.expires_at,
    )
