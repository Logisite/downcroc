from __future__ import annotations

import imaplib
import ssl

from imap_tools.errors import ImapToolsError

from downcroc.domain.providers import ProviderSpec
from downcroc.mail.imap.client import close, has_message_id, select_sent
from downcroc.mail.imap.connection import (
    ImapNetworkError,
    ImapProtocolError,
    ImapTlsError,
    authenticate,
    connect,
)

SENT_FLAG = "\\Sent"


def resolve_sent_folder(box, spec: ProviderSpec) -> str:
    """Pick the Sent folder by its special-use flag, not by name guessing.

    Gmail localizes folder names, so the configured ``spec.sent_folder`` is only
    the fallback when the server does not advertise RFC 6154 flags.
    """

    try:
        folders = box.folder.list()
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error
    for info in folders:
        if SENT_FLAG in info.flags and info.name:
            return info.name
    return spec.sent_folder or "Sent"


def find_sent(
    spec: ProviderSpec,
    address: str,
    message_id: str,
    *,
    password: str | None = None,
    access_token: str | None = None,
    timeout_s: float,
) -> bool:
    box = connect(spec, timeout_s)
    try:
        authenticate(
            box,
            address,
            password=password,
            access_token=access_token,
        )
        select_sent(box, spec.sent_folder)
        return has_message_id(box, message_id)
    finally:
        close(box)
