from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass

import aiosmtplib
from aiosmtplib import SMTP

from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec, TlsMode

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
    if not spec.smtp_host or not spec.smtp_port:
        raise SmtpFailure(
            "smtp_not_configured",
            "the provider has no smtp host",
            transient=False,
        )
    client = SMTP(
        hostname=spec.smtp_host,
        port=spec.smtp_port,
        timeout=timeout_s,
        use_tls=spec.smtp_tls is TlsMode.SSL,
        start_tls=spec.smtp_tls is TlsMode.STARTTLS,
    )
    connected_at = 0.0
    accepted_at = 0.0
    try:
        started = time.monotonic()
        await client.connect()
        connected_at = time.monotonic()
        if credentials.auth_kind is AuthKind.OAUTH2:
            await client.auth_xoauth2(
                credentials.address,
                credentials.access_token or "",
                timeout=timeout_s,
            )
        else:
            await client.login(
                credentials.address,
                credentials.password or "",
                timeout=timeout_s,
            )
        await client.mail(account.address)
        await client.rcpt(recipient)
        response = await client.data(message, timeout=timeout_s)
        accepted_at = time.monotonic()
        return SmtpSendResult(
            code=response.code,
            response=response.message,
            connect_ms=round((connected_at - started) * 1000),
            accepted_ms=round((accepted_at - started) * 1000),
        )
    except aiosmtplib.SMTPAuthenticationError as error:
        raise SmtpAuthFailure(f"smtp_{error.code}", _text(error.message)) from error
    except aiosmtplib.SMTPResponseException as error:
        raise _response_failure(error.code, _text(error.message)) from error
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as error:
        raise SmtpFailure(
            "smtp_network",
            str(error) or error.__class__.__name__,
            transient=True,
        ) from error
    finally:
        with contextlib.suppress(Exception):
            await client.quit()


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
