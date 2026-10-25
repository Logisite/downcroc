from __future__ import annotations

from downcroc.runtime.config.schema import (
    DispatchSettings,
    FollowUpSettings,
    SendingSettings,
)


def dispatch_config(
    *,
    daily_allowance: int = 200,
    window_start: int = 0,
    window_end: int = 24,
    jitter_min: int = 0,
    jitter_max: int = 0,
    max_in_flight: int = 2,
    log_level: str = "info",
    tick_s: float = 0.05,
    max_attempts: int = 3,
    retry_base_s: int = 1,
    retry_factor: float = 2.0,
    retry_cap_s: int = 4,
    retry_jitter: float = 0.0,
    global_in_flight: int = 8,
    lease_seconds: int = 120,
    reconcile_attempts: int = 1,
    followup_check_s: float = 0.05,
    followup_sync_timeout_s: float = 5.0,
    followup_defer_s: float = 1.0,
) -> str:
    defaults = DispatchSettings()
    followups = FollowUpSettings(
        check_s=followup_check_s,
        sync_timeout_s=followup_sync_timeout_s,
        defer_s=followup_defer_s,
    )
    sending = SendingSettings(
        daily_allowance=daily_allowance,
        window_start=window_start,
        window_end=window_end,
        jitter_min=jitter_min,
        jitter_max=jitter_max,
        max_in_flight=max_in_flight,
    )
    return (
        f'[logging]\nlevel = "{log_level}"\n\n'
        "[sending]\n"
        f"daily_allowance = {sending.daily_allowance}\n"
        f"window_start = {sending.window_start}\n"
        f"window_end = {sending.window_end}\n"
        f"jitter_min = {sending.jitter_min}\n"
        f"jitter_max = {sending.jitter_max}\n"
        f"max_in_flight = {sending.max_in_flight}\n\n"
        "[outbound]\n"
        f"lease_seconds = {lease_seconds}\n"
        f"reconcile_attempts = {reconcile_attempts}\n\n"
        "[dispatch]\n"
        f"tick_s = {tick_s}\n"
        f"max_attempts = {max_attempts}\n"
        f"retry_base_s = {retry_base_s}\n"
        f"retry_factor = {retry_factor}\n"
        f"retry_cap_s = {retry_cap_s}\n"
        f"retry_jitter = {retry_jitter}\n"
        f"global_in_flight = {global_in_flight}\n"
        f"shutdown_join_s = {defaults.shutdown_join_s}\n"
        "\n[followups]\n"
        f"check_s = {followups.check_s}\n"
        f"sync_timeout_s = {followups.sync_timeout_s}\n"
        f"defer_s = {followups.defer_s}\n"
    )
