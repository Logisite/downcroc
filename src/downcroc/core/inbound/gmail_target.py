from __future__ import annotations

from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account


def project_id(clients: OAuthClientService, account: Account) -> str | None:
    client_id = clients.account_client(account)
    if client_id is None:
        return None
    try:
        return clients.get(client_id).project_id
    except Exception:  # noqa: BLE001 - a missing client has no project
        return None
