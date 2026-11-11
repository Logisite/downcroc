from __future__ import annotations

import re
from dataclasses import dataclass

from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec

_AUTH_CODES = frozenset({530, 534, 535})
_PERMANENT_CODES = frozenset({550, 551, 552, 553, 554})
_TRANSIENT_CODES = frozenset({421, 450, 451, 452})
_ENHANCED = re.compile(r"\b([245]\.\d{1,3}\.\d{1,3})\b")
_RETRY = re.compile(r"retry(?:-|\s+)after[:\s]+(\d+)", re.IGNORECASE)


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
    def __init__(
        self,
        code: str,
        message: str,
        *,
        transient: bool,
        uncertain: bool = False,
        quota: bool = False,
        policy: bool = False,
        enhanced: str | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.transient = transient
        self.uncertain = uncertain
        self.quota = quota
        self.policy = policy
        self.enhanced = enhanced
        self.retry_after_s = retry_after_s
        self.detail = message[:500]


class SmtpAuthFailure(SmtpFailure):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        enhanced: str | None = None,
    ) -> None:
        super().__init__(code, message, transient=False, enhanced=enhanced)


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
    enhanced = _enhanced(message)
    text = message.casefold()
    retry = _retry_after(message)
    if code in _AUTH_CODES:
        return SmtpAuthFailure(f"smtp_{code}", message, enhanced=enhanced)
    if (
        enhanced in {"5.4.5", "4.7.0"}
        or "daily user sending limit" in text
        or "rate limit" in text
    ):
        return SmtpFailure(
            "smtp_quota",
            message,
            transient=True,
            quota=True,
            enhanced=enhanced,
            retry_after_s=retry,
        )
    if enhanced == "5.1.1" or "unknown recipient" in text or "no such user" in text:
        return SmtpFailure(
            "smtp_recipient",
            message,
            transient=False,
            enhanced=enhanced,
        )
    if (
        enhanced in {"5.7.0", "5.7.1"}
        or "spam" in text
        or "policy" in text
        or "blocked" in text
    ):
        return SmtpFailure(
            "smtp_policy",
            message,
            transient=False,
            policy=True,
            enhanced=enhanced,
        )
    if code in _TRANSIENT_CODES:
        return SmtpFailure(
            f"smtp_{code}",
            message,
            transient=True,
            enhanced=enhanced,
        )
    if enhanced == "5.2.2" or "mailbox full" in text:
        return SmtpFailure(
            "smtp_mailbox_full",
            message,
            transient=True,
            enhanced=enhanced,
        )
    if code in _PERMANENT_CODES:
        return SmtpFailure(
            f"smtp_{code}",
            message,
            transient=False,
            enhanced=enhanced,
        )
    return SmtpFailure(
        f"smtp_{code}",
        message,
        transient=True,
        enhanced=enhanced,
    )


def _enhanced(message: str) -> str | None:
    match = _ENHANCED.search(message)
    return match.group(1) if match else None


def _retry_after(message: str) -> int | None:
    match = _RETRY.search(message)
    return int(match.group(1)) if match else None


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
