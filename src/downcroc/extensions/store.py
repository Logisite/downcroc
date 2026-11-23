from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import ExtensionKvRow, ExtensionStateRow


class ExtensionStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def kv_get(self, extension: str, key: str) -> str | None:
        with self._sessions() as session:
            row = session.get(ExtensionKvRow, (extension, key))
            return row.value if row is not None else None

    def kv_set(self, extension: str, key: str, value: str) -> None:
        with self._sessions.begin() as session:
            row = session.get(ExtensionKvRow, (extension, key))
            if row is None:
                session.add(
                    ExtensionKvRow(extension_id=extension, key=key, value=value)
                )
            else:
                row.value = value

    def kv_delete(self, extension: str, key: str) -> None:
        with self._sessions.begin() as session:
            session.execute(
                delete(ExtensionKvRow).where(
                    ExtensionKvRow.extension_id == extension,
                    ExtensionKvRow.key == key,
                )
            )

    def kv_list(self, extension: str) -> dict[str, str]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ExtensionKvRow).where(ExtensionKvRow.extension_id == extension)
            )
            return {row.key: row.value for row in rows}

    def state(self, extension: str) -> dict[str, object] | None:
        with self._sessions() as session:
            row = session.get(ExtensionStateRow, extension)
            if row is None:
                return None
            return {
                "id": row.id,
                "version": row.version,
                "enabled": bool(row.enabled),
                "restarts": row.restarts,
                "last_error": row.last_error,
            }

    def save_state(
        self,
        extension: str,
        *,
        version: str,
        enabled: bool,
        restarts: int = 0,
        last_error: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            row = session.get(ExtensionStateRow, extension)
            if row is None:
                session.add(
                    ExtensionStateRow(
                        id=extension,
                        version=version,
                        enabled=int(enabled),
                        restarts=restarts,
                        last_error=last_error,
                        updated_at=utc_now(),
                    )
                )
                return
            row.version = version
            row.enabled = int(enabled)
            row.restarts = restarts
            row.last_error = last_error
            row.updated_at = utc_now()

    def remove_state(self, extension: str) -> None:
        with self._sessions.begin() as session:
            row = session.get(ExtensionStateRow, extension)
            if row is not None:
                session.delete(row)
