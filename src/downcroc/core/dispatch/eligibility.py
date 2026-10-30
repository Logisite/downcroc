from __future__ import annotations

from datetime import datetime

from downcroc.domain.policy import SendPolicy


def inside_window(policy: SendPolicy, moment: datetime) -> bool:
    hour = moment.hour
    if policy.window_start < policy.window_end:
        return policy.window_start <= hour < policy.window_end
    return hour >= policy.window_start or hour < policy.window_end
