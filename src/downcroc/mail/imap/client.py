from __future__ import annotations

import calendar
import contextlib
import imaplib
import ssl
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from imap_tools import MailBox, MailMessage
from imap_tools.errors import ImapToolsError

from downcroc.mail.imap.connection import (
    ImapNetworkError,
    ImapProtocolError,
    ImapTlsError,
)

INBOX = "INBOX"


@dataclass(frozen=True)
class InboxState:
    uidvalidity: int
    uidnext: int
    messages: int


def select_inbox(box: MailBox) -> InboxState:
    try:
        box.folder.set(INBOX, readonly=True)
        status = box.folder.status(
            INBOX, options=("UIDVALIDITY", "UIDNEXT", "MESSAGES")
        )
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error
    return InboxState(
        uidvalidity=int(status.get("UIDVALIDITY", 0)),
        uidnext=int(status.get("UIDNEXT", 0)),
        messages=int(status.get("MESSAGES", 0)),
    )


def search_new(box: MailBox, last_uid: int) -> list[int]:
    uids = _search(box, f"UID {last_uid + 1}:*")
    return [uid for uid in uids if uid > last_uid]


def search_initial(box: MailBox, days: int, limit: int) -> list[int]:
    criteria = "ALL"
    if days > 0:
        moment = datetime.now(UTC) - timedelta(days=days)
        stamp = f"{moment.day:02d}-{calendar.month_abbr[moment.month]}-{moment.year}"
        criteria = f"SINCE {stamp}"
    uids = _search(box, criteria)
    return uids[-limit:]


def search_all(box: MailBox) -> list[int]:
    return _search(box, "ALL")


def select_sent(box: MailBox, folder: str) -> None:
    try:
        box.folder.set(folder or "Sent", readonly=True)
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error


def has_message_id(box: MailBox, message_id: str) -> bool:
    criteria = f'HEADER "Message-ID" "<{message_id.strip("<>")}>"'
    return bool(_search(box, criteria))


def fetch_messages(
    box: MailBox,
    uids: list[int],
    batch: int,
) -> Iterator[MailMessage]:
    if not uids:
        return
    try:
        yield from box.fetch(
            uid_list=[str(uid) for uid in uids],
            mark_seen=False,
            bulk=batch if batch > 1 else False,
        )
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error


def close(box: MailBox) -> None:
    with contextlib.suppress(imaplib.IMAP4.error, OSError, ImapToolsError):
        box.logout()


def _search(box: MailBox, criteria: str) -> list[int]:
    try:
        raw = box.uids(criteria)
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError) as error:
        raise ImapNetworkError from error
    except imaplib.IMAP4.abort as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error
    found: list[int] = []
    for item in raw:
        try:
            found.append(int(item))
        except ValueError:
            continue
    return sorted(set(found))
