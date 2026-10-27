from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.runtime.config.sections_mail import (
    ConfigSettings,
    ConnectSettings,
    EventsSettings,
    InboundSettings,
    IntakeSettings,
    OutboundSettings,
    VaultSettings,
)
from downcroc.runtime.config.sections_runtime import (
    CliSettings,
    DaemonSettings,
    DispatchSettings,
    FollowUpSettings,
    LoggingSettings,
    RetentionSettings,
    SendingSettings,
)

__all__ = [
    "CliSettings",
    "ConfigSettings",
    "ConnectSettings",
    "DaemonSettings",
    "DispatchSettings",
    "EventsSettings",
    "FollowUpSettings",
    "InboundSettings",
    "IntakeSettings",
    "LoggingSettings",
    "OutboundSettings",
    "RetentionSettings",
    "SendingSettings",
    "Settings",
    "VaultSettings",
]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daemon: DaemonSettings = Field(
        default_factory=DaemonSettings,
        description="HTTP daemon settings.",
    )
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Daemon log settings.",
    )
    sending: SendingSettings = Field(
        default_factory=SendingSettings,
        description="Sending defaults copied into new accounts.",
    )
    dispatch: DispatchSettings = Field(
        default_factory=DispatchSettings,
        description="Dispatcher loop, retry, and concurrency settings.",
    )
    followups: FollowUpSettings = Field(
        default_factory=FollowUpSettings,
        description="Follow-up planning settings.",
    )
    retention: RetentionSettings = Field(
        default_factory=RetentionSettings,
        description="Retention and pruning settings.",
    )
    events: EventsSettings = Field(
        default_factory=EventsSettings,
        description="Event ring and stream settings.",
    )
    vault: VaultSettings = Field(
        default_factory=VaultSettings,
        description="Vault key derivation and throttle settings.",
    )
    connect: ConnectSettings = Field(
        default_factory=ConnectSettings,
        description="OAuth and IMAP connection settings.",
    )
    inbound: InboundSettings = Field(
        default_factory=InboundSettings,
        description="Inbound watcher and ingest settings.",
    )
    outbound: OutboundSettings = Field(
        default_factory=OutboundSettings,
        description="Outbound send and reconciliation settings.",
    )
    intake: IntakeSettings = Field(
        default_factory=IntakeSettings,
        description="Campaign input and attachment limits.",
    )
    config: ConfigSettings = Field(
        default_factory=ConfigSettings,
        description="Configuration reload settings.",
    )
    cli: CliSettings = Field(
        default_factory=CliSettings,
        description="Command line client behaviour.",
    )
