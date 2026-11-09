from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConnectivitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Watch for internet outages and pause network work while offline.",
    )
    probe_host: str = Field(
        default="1.1.1.1",
        description="Host for the TCP reachability probe.",
    )
    probe_port: int = Field(
        default=443,
        ge=1,
        le=65535,
        description="Port for the TCP reachability probe.",
    )
    interval_s: float = Field(
        default=15.0,
        gt=0,
        le=3600,
        description="Seconds between reachability probes.",
    )
    jitter_s: float = Field(
        default=5.0,
        ge=0,
        le=3600,
        description="Maximum extra random delay added to each probe interval.",
    )
    timeout_s: float = Field(
        default=3.0,
        gt=0,
        le=60,
        description="Seconds a single probe waits before it counts as failed.",
    )
    confirm_failures: int = Field(
        default=3,
        ge=1,
        le=20,
        description=(
            "Consecutive failed probes needed to call the internet down, so "
            "a brief blip never pauses anything."
        ),
    )
    confirm_successes: int = Field(
        default=3,
        ge=1,
        le=20,
        description=("Consecutive successful probes needed to resume after an outage."),
    )
