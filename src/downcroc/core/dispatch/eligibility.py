from __future__ import annotations

from datetime import datetime

from downcroc.domain.accounts import SendPolicy


def local_now() -> datetime:
    return datetime.now().astimezone()


def day_key(moment: datetime) -> str:
    return moment.date().isoformat()


def inside_window(policy: SendPolicy, moment: datetime) -> bool:
    hour = moment.hour
    if policy.window_start < policy.window_end:
        return policy.window_start <= hour < policy.window_end
    return hour >= policy.window_start or hour < policy.window_end
