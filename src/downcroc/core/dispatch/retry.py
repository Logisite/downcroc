from __future__ import annotations

import random

from downcroc.runtime.config.schema import DispatchSettings


def backoff_seconds(
    attempt: int,
    settings: DispatchSettings,
    rng: random.Random,
) -> int:
    raw = settings.retry_base_s * (settings.retry_factor ** max(0, attempt - 1))
    capped = min(raw, settings.retry_cap_s)
    spread = capped * settings.retry_jitter
    low = max(1.0, capped - spread)
    high = max(low, capped + spread)
    return max(1, round(rng.uniform(low, high)))
