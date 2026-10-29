from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttemptResult:
    status: str
    code: str | None = None
    message: str | None = None
    transient: bool = False
    auth: bool = False
    provider_message_id: str | None = None

    @classmethod
    def sent(cls, provider_message_id: str | None = None) -> AttemptResult:
        return cls("sent", provider_message_id=provider_message_id)

    @classmethod
    def failed(
        cls,
        code: str,
        message: str,
        *,
        auth: bool = False,
    ) -> AttemptResult:
        return cls("failed", code=code, message=message, auth=auth)

    @classmethod
    def deferred(cls, code: str, message: str) -> AttemptResult:
        return cls("deferred", code=code, message=message, transient=True)

    @classmethod
    def uncertain(cls, code: str, message: str) -> AttemptResult:
        return cls("uncertain", code=code, message=message, transient=True)
