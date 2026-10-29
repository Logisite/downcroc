from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field

import aiosmtplib
from aiosmtplib import SMTP

from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec, TlsMode
from downcroc.mail.smtp.sender import (
    SmtpAuthFailure,
    SmtpCredentials,
    SmtpFailure,
    SmtpSendResult,
    _response_failure,
    _text,
)
from downcroc.runtime.config.schema import OutboundSettings
from downcroc.runtime.logging.setup import EventLogger


class SmtpSession:
    def __init__(
        self,
        spec: ProviderSpec,
        account: Account,
        credentials: SmtpCredentials,
        timeout_s: float,
    ) -> None:
        self._spec = spec
        self._account = account
        self._credentials = credentials
        self._timeout_s = timeout_s
        self._client: SMTP | None = None
        self._fingerprint = (
            credentials.address,
            credentials.auth_kind.value,
            credentials.password or credentials.access_token or "",
        )
        self.messages = 0
        self._connect_ms = 0

    @property
    def fingerprint(self) -> tuple[str, str, str]:
        return self._fingerprint

    @property
    def open(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        spec = self._spec
        if not spec.smtp_host or not spec.smtp_port:
            raise SmtpFailure(
                "smtp_not_configured",
                "the provider has no smtp host",
                transient=False,
            )
        client = SMTP(
            hostname=spec.smtp_host,
            port=spec.smtp_port,
            timeout=self._timeout_s,
            use_tls=spec.smtp_tls is TlsMode.SSL,
            start_tls=spec.smtp_tls is TlsMode.STARTTLS,
        )
        started = time.monotonic()
        try:
            await client.connect()
            if self._credentials.auth_kind is AuthKind.OAUTH2:
                await client.auth_xoauth2(
                    self._credentials.address,
                    self._credentials.access_token or "",
                    timeout=self._timeout_s,
                )
            else:
                await client.login(
                    self._credentials.address,
                    self._credentials.password or "",
                    timeout=self._timeout_s,
                )
        except aiosmtplib.SMTPAuthenticationError as error:
            await self._close_client(client)
            raise SmtpAuthFailure(f"smtp_{error.code}", _text(error.message)) from error
        except aiosmtplib.SMTPResponseException as error:
            await self._close_client(client)
            raise _response_failure(error.code, _text(error.message)) from error
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as error:
            await self._close_client(client)
            raise SmtpFailure(
                "smtp_network",
                str(error) or error.__class__.__name__,
                transient=True,
            ) from error
        self._client = client
        self._connect_ms = round((time.monotonic() - started) * 1000)

    async def noop(self) -> None:
        client = self._require()
        try:
            await client.noop(timeout=self._timeout_s)
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as error:
            raise SmtpFailure(
                "smtp_network",
                str(error) or error.__class__.__name__,
                transient=True,
            ) from error

    async def send(self, recipient: str, message: bytes) -> SmtpSendResult:
        client = self._require()
        started = time.monotonic()
        try:
            await client.mail(self._account.address, timeout=self._timeout_s)
            await client.rcpt(recipient, timeout=self._timeout_s)
            response = await client.data(message, timeout=self._timeout_s)
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
        accepted_at = time.monotonic()
        self.messages += 1
        connect_ms = self._connect_ms
        self._connect_ms = 0
        return SmtpSendResult(
            code=response.code,
            response=response.message,
            connect_ms=connect_ms,
            accepted_ms=round((accepted_at - started) * 1000),
        )

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            await client.quit()
        except aiosmtplib.SMTPException, OSError, TimeoutError:
            await self._close_client(client)

    @staticmethod
    async def _close_client(client: SMTP) -> None:
        with contextlib.suppress(Exception):
            client.close()

    def _require(self) -> SMTP:
        if self._client is None:
            raise SmtpFailure("smtp_network", "the session is closed", transient=True)
        return self._client


@dataclass
class _Entry:
    session: SmtpSession
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)
    last_check: float = field(default_factory=time.monotonic)


class SmtpSessionPool:
    def __init__(self, settings: OutboundSettings, log: EventLogger) -> None:
        self._settings = settings
        self._log = log
        self._entries: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def send(
        self,
        binding_id: str,
        spec: ProviderSpec,
        account: Account,
        credentials: SmtpCredentials,
        recipient: str,
        message: bytes,
        *,
        timeout_s: float,
    ) -> SmtpSendResult:
        if not self._settings.keepalive:
            return await self._one_shot(
                spec, account, credentials, recipient, message, timeout_s
            )
        lock = self._locks.setdefault(binding_id, asyncio.Lock())
        async with lock:
            entry = self._entries.get(binding_id)
            if entry is not None and self._stale(entry, credentials):
                await self._drop(binding_id, entry, "stale")
                entry = None
            if entry is not None:
                entry = await self._verify(binding_id, entry)
            if entry is None:
                session = await self._open(spec, account, credentials, timeout_s)
                entry = _Entry(session)
                self._entries[binding_id] = entry
            else:
                self._log.info(
                    "smtp.session_reused",
                    account=account.id,
                    binding=binding_id,
                    messages=entry.session.messages,
                )
            try:
                result = await entry.session.send(recipient, message)
            except SmtpFailure:
                await self._drop(binding_id, entry, "send_failed")
                raise
            entry.last_used = time.monotonic()
            return result

    async def reap(self) -> None:
        now = time.monotonic()
        idle = self._settings.keepalive_idle_s
        for binding_id, entry in list(self._entries.items()):
            if entry.lock.locked():
                continue
            if now - entry.last_used < idle:
                continue
            async with entry.lock:
                if self._entries.get(binding_id) is entry:
                    await self._drop(binding_id, entry, "idle")

    async def close_all(self, reason: str) -> None:
        for binding_id, entry in list(self._entries.items()):
            await self._drop(binding_id, entry, reason)

    async def prune(self, valid: set[str], reason: str = "binding_removed") -> None:
        for binding_id, entry in list(self._entries.items()):
            if binding_id not in valid:
                await self._drop(binding_id, entry, reason)

    async def _verify(self, binding_id: str, entry: _Entry) -> _Entry | None:
        now = time.monotonic()
        if now - entry.last_check < self._settings.keepalive_noop_s:
            return entry
        try:
            await entry.session.noop()
        except SmtpFailure as error:
            self._log.info(
                "smtp.session_dropped",
                binding=binding_id,
                reason=error.code,
            )
            await self._drop(binding_id, entry, error.code)
            return None
        entry.last_check = now
        return entry

    async def _drop(self, binding_id: str, entry: _Entry, reason: str) -> None:
        if self._entries.get(binding_id) is entry:
            del self._entries[binding_id]
        await entry.session.close()
        self._log.info(
            "smtp.session_closed",
            binding=binding_id,
            reason=reason,
            messages=entry.session.messages,
        )

    async def _open(
        self,
        spec: ProviderSpec,
        account: Account,
        credentials: SmtpCredentials,
        timeout_s: float,
    ) -> SmtpSession:
        session = SmtpSession(spec, account, credentials, timeout_s)
        await session.connect()
        self._log.info(
            "smtp.session_open",
            account=account.id,
            host=spec.smtp_host,
        )
        return session

    async def _one_shot(
        self,
        spec: ProviderSpec,
        account: Account,
        credentials: SmtpCredentials,
        recipient: str,
        message: bytes,
        timeout_s: float,
    ) -> SmtpSendResult:
        session = SmtpSession(spec, account, credentials, timeout_s)
        await session.connect()
        try:
            return await session.send(recipient, message)
        finally:
            await session.close()

    def _stale(self, entry: _Entry, credentials: SmtpCredentials) -> bool:
        if entry.session.fingerprint[2] != (
            credentials.password or credentials.access_token or ""
        ):
            return True
        idle = time.monotonic() - entry.last_used
        return idle >= self._settings.keepalive_idle_s
