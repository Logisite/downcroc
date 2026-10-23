from __future__ import annotations

from downcroc.domain.providers import ProviderSpec
from downcroc.mail.imap.client import close, has_message_id, select_sent
from downcroc.mail.imap.connection import authenticate, connect


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
