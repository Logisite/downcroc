from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.campaign import FollowUpOverride
from downcroc.domain.errors import (
    FollowUpNotFound,
    FollowUpStepExists,
    FollowUpVersionConflict,
)
from downcroc.domain.followups import (
    DeclarationKind,
    DeclarationState,
    FollowUpDeclaration,
)
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import FollowUpDeclarationRow


def _to_declaration(row: FollowUpDeclarationRow) -> FollowUpDeclaration:
    return FollowUpDeclaration(
        id=row.id,
        batch_id=row.batch_id,
        step_key=row.step_key,
        kind=DeclarationKind(row.kind),
        after_days=row.after_days,
        when=row.when,
        subject=row.subject,
        text=row.text,
        html=row.html,
        require_approval=bool(row.require_approval),
        overrides=_overrides(row.overrides_json),
        content_ref=row.content_ref,
        content_hash=row.content_hash,
        state=DeclarationState(row.state),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _overrides(raw: str) -> dict[str, FollowUpOverride]:
    try:
        loaded = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    overrides: dict[str, FollowUpOverride] = {}
    for key, value in loaded.items():
        if not isinstance(value, dict):
            continue
        overrides[str(key)] = FollowUpOverride(
            subject=_text(value.get("subject")),
            text=_text(value.get("text")),
            html=_text(value.get("html")),
            skip=value.get("skip") is True,
        )
    return overrides


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


class FollowUpDeclarationRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self, batch_id: str, step_key: str) -> FollowUpDeclaration | None:
        with self._sessions() as session:
            row = session.scalar(
                select(FollowUpDeclarationRow).where(
                    FollowUpDeclarationRow.batch_id == batch_id,
                    FollowUpDeclarationRow.step_key == step_key,
                )
            )
            return None if row is None else _to_declaration(row)

    def list_for_batch(self, batch_id: str) -> list[FollowUpDeclaration]:
        with self._sessions() as session:
            rows = session.scalars(
                select(FollowUpDeclarationRow)
                .where(FollowUpDeclarationRow.batch_id == batch_id)
                .order_by(
                    FollowUpDeclarationRow.created_at,
                    FollowUpDeclarationRow.step_key,
                )
            )
            return [_to_declaration(row) for row in rows]

    def list_active(self) -> dict[str, list[FollowUpDeclaration]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(FollowUpDeclarationRow)
                .where(FollowUpDeclarationRow.state == DeclarationState.ACTIVE.value)
                .order_by(
                    FollowUpDeclarationRow.batch_id,
                    FollowUpDeclarationRow.created_at,
                    FollowUpDeclarationRow.step_key,
                )
            )
            found: dict[str, list[FollowUpDeclaration]] = {}
            for row in rows:
                found.setdefault(row.batch_id, []).append(_to_declaration(row))
            return found

    def create(self, declaration: FollowUpDeclaration) -> FollowUpDeclaration:
        row = _row(declaration)
        try:
            with self._sessions.begin() as session:
                session.add(row)
        except IntegrityError as error:
            raise FollowUpStepExists(
                f"step {declaration.step_key} is already declared",
                hint="choose a new step key such as fu1b",
            ) from error
        return self._required(declaration.batch_id, declaration.step_key)

    def update(
        self,
        declaration: FollowUpDeclaration,
        expected_version: int,
    ) -> FollowUpDeclaration:
        with self._sessions.begin() as session:
            row = self._row(session, declaration.batch_id, declaration.step_key)
            _require_version(row, expected_version)
            row.kind = declaration.kind.value
            row.after_days = declaration.after_days
            row.when = declaration.when
            row.subject = declaration.subject
            row.text = declaration.text
            row.html = declaration.html
            row.require_approval = int(declaration.require_approval)
            row.overrides_json = json.dumps(
                _override_documents(declaration.overrides),
                sort_keys=True,
                separators=(",", ":"),
            )
            row.content_ref = declaration.content_ref
            row.content_hash = declaration.content_hash
            row.state = declaration.state.value
            row.version += 1
            row.updated_at = utc_now()
        return self._required(declaration.batch_id, declaration.step_key)

    def set_state(
        self,
        batch_id: str,
        step_key: str,
        state: DeclarationState,
        *,
        expected_version: int | None = None,
    ) -> FollowUpDeclaration:
        with self._sessions.begin() as session:
            row = self._row(session, batch_id, step_key)
            if expected_version is not None:
                _require_version(row, expected_version)
            row.state = state.value
            row.version += 1
            row.updated_at = utc_now()
        return self._required(batch_id, step_key)

    def delete(self, batch_id: str, step_key: str) -> bool:
        with self._sessions.begin() as session:
            result = session.execute(
                delete(FollowUpDeclarationRow).where(
                    FollowUpDeclarationRow.batch_id == batch_id,
                    FollowUpDeclarationRow.step_key == step_key,
                )
            )
            return bool(result.rowcount)

    def _required(self, batch_id: str, step_key: str) -> FollowUpDeclaration:
        found = self.get(batch_id, step_key)
        if found is None:
            raise FollowUpNotFound(f"no follow-up step {step_key}")
        return found

    def _row(
        self, session: Session, batch_id: str, step_key: str
    ) -> FollowUpDeclarationRow:
        row = session.scalar(
            select(FollowUpDeclarationRow).where(
                FollowUpDeclarationRow.batch_id == batch_id,
                FollowUpDeclarationRow.step_key == step_key,
            )
        )
        if row is None:
            raise FollowUpNotFound(f"no follow-up step {step_key}")
        return row


def _require_version(row: FollowUpDeclarationRow, expected: int) -> None:
    if row.version != expected:
        raise FollowUpVersionConflict(
            f"step {row.step_key} is at version {row.version}",
            hint=f"re-read the status and retry with version {row.version}",
            fields={"version": str(expected)},
        )


def _row(declaration: FollowUpDeclaration) -> FollowUpDeclarationRow:
    return FollowUpDeclarationRow(
        id=declaration.id,
        batch_id=declaration.batch_id,
        step_key=declaration.step_key,
        kind=declaration.kind.value,
        after_days=declaration.after_days,
        when=declaration.when,
        subject=declaration.subject,
        text=declaration.text,
        html=declaration.html,
        require_approval=int(declaration.require_approval),
        overrides_json=json.dumps(
            _override_documents(declaration.overrides),
            sort_keys=True,
            separators=(",", ":"),
        ),
        content_ref=declaration.content_ref,
        content_hash=declaration.content_hash,
        state=declaration.state.value,
        version=declaration.version,
        created_at=declaration.created_at,
        updated_at=declaration.updated_at,
    )


def _override_documents(
    overrides: dict[str, FollowUpOverride],
) -> dict[str, dict[str, object]]:
    documents: dict[str, dict[str, object]] = {}
    for key, override in overrides.items():
        document: dict[str, object] = {}
        if override.skip:
            document["skip"] = True
        if override.subject is not None:
            document["subject"] = override.subject
        if override.text is not None:
            document["text"] = override.text
        if override.html is not None:
            document["html"] = override.html
        documents[key] = document
    return documents
