from __future__ import annotations

import contextlib
import imaplib
import ssl

from imap_tools import MailBox
from imap_tools.errors import ImapToolsError, MailboxLoginError

from downcroc.domain.providers import ProviderSpec, TlsMode


class ImapAuthError(Exception):
    pass


class ImapNetworkError(Exception):
    pass


class ImapTlsError(Exception):
    pass


class ImapProtocolError(Exception):
    pass


class _PlainMailBox(MailBox):
    def _get_mailbox_client(self) -> imaplib.IMAP4:
        return imaplib.IMAP4(self._host, self._port, timeout=self._timeout)


class _StartTlsMailBox(MailBox):
    def _get_mailbox_client(self) -> imaplib.IMAP4:
        client = imaplib.IMAP4(self._host, self._port, timeout=self._timeout)
        client.starttls(ssl.create_default_context())
        return client


def authenticate(
    box: MailBox,
    address: str,
    *,
    password: str | None = None,
    access_token: str | None = None,
) -> None:
    try:
        if access_token is not None:
            box.xoauth2(address, access_token, initial_folder=None)
        else:
            box.login(address, password or "", initial_folder=None)
    except MailboxLoginError as error:
        raise ImapAuthError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.error as error:
        raise ImapAuthError from error
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except ImapToolsError as error:
        raise ImapNetworkError from error


def login(
    spec: ProviderSpec,
    address: str,
    *,
    password: str | None = None,
    access_token: str | None = None,
    timeout_s: float,
) -> None:
    box = connect(spec, timeout_s)
    try:
        authenticate(
            box,
            address,
            password=password,
            access_token=access_token,
        )
    finally:
        with contextlib.suppress(
            MailboxLoginError, imaplib.IMAP4.error, OSError, ImapToolsError
        ):
            box.logout()


def connect(spec: ProviderSpec, timeout_s: float) -> MailBox:
    try:
        if spec.imap_tls is TlsMode.SSL:
            return MailBox(spec.imap_host, spec.imap_port, timeout=timeout_s)
        if spec.imap_tls is TlsMode.STARTTLS:
            return _StartTlsMailBox(spec.imap_host, spec.imap_port, timeout=timeout_s)
        return _PlainMailBox(spec.imap_host, spec.imap_port, timeout=timeout_s)
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.error as error:
        raise ImapNetworkError from error
    except ImapToolsError as error:
        raise ImapNetworkError from error
