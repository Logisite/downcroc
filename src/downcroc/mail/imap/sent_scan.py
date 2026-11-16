from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass, field
from email.parser import BytesHeaderParser

from imap_tools import MailBox
from imap_tools.errors import ImapToolsError

from downcroc.domain.messages import normalize_message_id
from downcroc.mail.imap.connection import (
    ImapNetworkError,
    ImapProtocolError,
    ImapTlsError,
)

GM_EXT = "X-GM-EXT-1"
_THRID = re.compile(rb"X-GM-THRID (\d+)")
_UID = re.compile(rb"UID (\d+)")
_FETCH_ITEMS = "(UID X-GM-THRID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"


@dataclass(frozen=True)
class SweepResult:
    """Read-only Sent sweep outcome: message id to candidate hex thread ids."""

    messages: int
    threads: dict[str, set[str]] = field(default_factory=dict)


def has_gmail_extensions(box: MailBox) -> bool:
    capabilities = getattr(box.client, "capabilities", None) or ()
    return GM_EXT in capabilities


def sweep(
    box: MailBox,
    chunk: int,
    *,
    pace=None,
) -> SweepResult:
    """Fetch X-GM-THRID plus Message-ID for every UID in the selected folder.

    The caller selects the Sent folder readonly before calling. ``BODY.PEEK``
    keeps the sweep from touching ``\\Seen`` or any other flag. ``pace`` runs
    after each chunk so the worker can spread the load.
    """

    uids = _uid_list(box)
    threads: dict[str, set[str]] = {}
    seen = 0
    for start in range(0, len(uids), chunk):
        seen += _fetch_chunk(box, uids[start : start + chunk], threads)
        if pace is not None:
            pace(seen)
    return SweepResult(messages=seen, threads=threads)


def _uid_list(box: MailBox) -> list[int]:
    try:
        status, data = box.client.uid("SEARCH", "ALL")
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError, imaplib.IMAP4.abort) as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error
    if status != "OK" or not data or data[0] is None:
        return []
    return sorted(int(item) for item in data[0].split() if item.isdigit())


def _fetch_chunk(
    box: MailBox,
    uids: list[int],
    threads: dict[str, set[str]],
) -> int:
    if not uids:
        return 0
    span = f"{uids[0]}:{uids[-1]}"
    try:
        status, data = box.client.uid("FETCH", span, _FETCH_ITEMS)
    except ssl.SSLError as error:
        raise ImapTlsError from error
    except (OSError, TimeoutError, imaplib.IMAP4.abort) as error:
        raise ImapNetworkError from error
    except (imaplib.IMAP4.error, ImapToolsError) as error:
        raise ImapProtocolError from error
    if status != "OK":
        raise ImapProtocolError(f"uid fetch failed with {status}")
    seen = 0
    for item in data or ():
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        hit = _parse_entry(item[0], item[1])
        if hit is None:
            continue
        seen += 1
        threads.setdefault(hit[0], set()).add(hit[1])
    return seen


def _parse_entry(meta: object, literal: object) -> tuple[str, str] | None:
    if not isinstance(meta, bytes) or not isinstance(literal, bytes):
        return None
    thrid = _THRID.search(meta)
    uid = _UID.search(meta)
    if thrid is None or uid is None:
        return None
    message_id = normalize_message_id(
        BytesHeaderParser().parsebytes(literal).get("Message-ID")
    )
    if message_id is None:
        return None
    return message_id, f"{int(thrid.group(1)):x}"
