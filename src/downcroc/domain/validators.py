from __future__ import annotations

import re

from downcroc.domain.errors import InvalidAccount

ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROVIDER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_account(provider: str, address: str, label: str) -> tuple[str, str, str]:
    provider = provider.strip().lower()
    address = address.strip().lower()
    label = label.strip() or address

    fields: dict[str, str] = {}
    if not PROVIDER.fullmatch(provider):
        fields["provider"] = (
            "must be a provider id, lowercase letters, digits, hyphen or underscore"
        )
    if not ADDRESS.fullmatch(address):
        fields["address"] = "must be an email address"
    if len(label) > 80:
        fields["label"] = "must be 80 characters or fewer"
    if fields:
        raise InvalidAccount("the account fields are not valid", fields=fields)
    return provider, address, label
