from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec

_AUTH_CODES = frozenset({530, 534, 535})
_PERMANENT_CODES = frozenset({550, 551, 552, 553, 554})


@dataclass(frozen=True)
class SmtpCredentials:
    address: str
    auth_kind: AuthKind
    password: str | None = None
    access_token: str | None = None


@dataclass(frozen=True)
class SmtpSendResult:
    code: int
    response: str
    connect_ms: int
    accepted_ms: int


class SmtpFailure(Exception):
    def __init__(self, code: str, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.transient = transient


class SmtpAuthFailure(SmtpFailure):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, transient=False)


async def send(
    spec: ProviderSpec,
    account: Account,
    credentials: SmtpCredentials,
    recipient: str,
    message: bytes,
    *,
    timeout_s: float,
) -> SmtpSendResult:
    from downcroc.mail.smtp.session import SmtpSession

    session = SmtpSession(spec, account, credentials, timeout_s)
    await session.connect()
    try:
        return await session.send(recipient, message)
    finally:
        await session.close()


async def test(
    spec: ProviderSpec,
    account: Account,
    credentials: SmtpCredentials,
    *,
    timeout_s: float,
) -> int:
    from downcroc.mail.smtp.session import SmtpSession

    session = SmtpSession(spec, account, credentials, timeout_s)
    await session.connect()
    try:
        await session.noop()
        return session.messages
    finally:
        await session.close()


def _response_failure(code: int, message: str) -> SmtpFailure:
    if code in _AUTH_CODES:
        return SmtpAuthFailure(f"smtp_{code}", message)
    if code in _PERMANENT_CODES:
        return SmtpFailure(f"smtp_{code}", message, transient=False)
    return SmtpFailure(f"smtp_{code}", message, transient=True)


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
