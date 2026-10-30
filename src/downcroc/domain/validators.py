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


def validate_policy(values: dict[str, object]) -> None:
    low = values.get("jitter_min")
    high = values.get("jitter_max")
    if isinstance(low, int) and isinstance(high, int) and high < low:
        raise ValueError("jitter_max must be at least jitter_min")
    start = values.get("window_start")
    end = values.get("window_end")
    if isinstance(start, int) and isinstance(end, int) and start == end:
        raise ValueError("window_start and window_end must differ")
