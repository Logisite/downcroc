from __future__ import annotations

from datetime import UTC, datetime


def parse(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def ago(value: object, *, now: datetime | None = None) -> str:
    moment = parse(value)
    if moment is None:
        return "-"
    current = now or datetime.now(UTC)
    seconds = max(0, int((current - moment).total_seconds()))
    return compact(seconds)


def in_time(value: object, *, now: datetime | None = None) -> str:
    moment = parse(value)
    if moment is None:
        return "-"
    current = now or datetime.now(UTC)
    delta = int((moment - current).total_seconds())
    if delta <= 0:
        return f"overdue {compact(abs(delta))}"
    return f"in {compact(delta)}"


def compact(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = round(seconds / 3600)
    if hours < 48:
        return f"{hours}h"
    days = round(seconds / 86400)
    if days < 45:
        return f"{days}d"
    months = round(days / 30)
    if months < 18:
        return f"{months}mo"
    years = round(days / 365)
    return f"{years}y"
