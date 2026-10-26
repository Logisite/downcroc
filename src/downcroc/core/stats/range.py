from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from downcroc.domain.errors import InvalidRange


@dataclass(frozen=True)
class StatsRange:
    start_day: str
    end_day: str
    start_hour: str
    end_hour: str


def local_today() -> date:
    return datetime.now().astimezone().date()


def parse_range(from_value: str | None, to_value: str | None) -> StatsRange:
    end = _date(to_value) or local_today()
    start = _date(from_value) or (end - timedelta(days=6))
    if start > end:
        raise InvalidRange(
            "from must not be after to",
            fields={"from": "must be on or before to"},
        )
    following = end + timedelta(days=1)
    return StatsRange(
        start_day=start.isoformat(),
        end_day=end.isoformat(),
        start_hour=f"{start.isoformat()}T00:00:00",
        end_hour=f"{following.isoformat()}T00:00:00",
    )


def parse_day(value: str | None) -> date | None:
    return _date(value)


def _date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise InvalidRange(
            "the date is not valid",
            fields={"date": "use YYYY-MM-DD or an ISO timestamp"},
        ) from error
