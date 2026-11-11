from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from downcroc.domain.campaign import FollowUpOverride, FollowUpStep


class DeclarationKind(StrEnum):
    SHARED = "shared"
    PAYLOAD = "payload"


class DeclarationState(StrEnum):
    ACTIVE = "active"
    REMOVING = "removing"
    RETIRED = "retired"


@dataclass(frozen=True)
class FollowUpDeclaration:
    id: str
    batch_id: str
    step_key: str
    kind: DeclarationKind
    after_days: int
    when: str
    subject: str | None
    text: str | None
    html: str | None
    require_approval: bool
    overrides: dict[str, FollowUpOverride]
    content_ref: str | None
    content_hash: str | None
    state: DeclarationState
    version: int
    created_at: str
    updated_at: str

    def step(self) -> FollowUpStep:
        return FollowUpStep(
            key=self.step_key,
            after_days=self.after_days,
            when=self.when,
            subject=self.subject,
            text=self.text or "",
            html=self.html,
            require_approval=self.require_approval,
        )
