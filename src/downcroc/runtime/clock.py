from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

OFFSET = re.compile(r"^(?:UTC)?([+-])(\d{1,2})(?::?(\d{2}))?$")


def zone_for(value: str) -> tzinfo:
    """Resolve an IANA name or a UTC offset such as +1, -3, or +05:30."""
    text = value.strip()
    if text.upper() == "UTC":
        return UTC
    match = OFFSET.fullmatch(text.upper())
    if match is None:
        return ZoneInfo(text)
    sign = -1 if match.group(1) == "-" else 1
    hours = int(match.group(2))
    minutes = int(match.group(3) or 0)
    if hours > 14 or minutes > 59:
        raise ValueError("the utc offset is out of range")
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(sign * delta)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def utc_after(seconds: float) -> str:
    moment = datetime.now(UTC) + timedelta(seconds=seconds)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)
