from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA = "downcroc.campaign/v1"
APPROVAL_MODES = frozenset({"review", "auto"})
ROUTING_MODES = frozenset({"auto", "fixed"})
STOP_REASONS = frozenset({"reply", "bounce"})
FOLLOWUP_WHEN = frozenset({"no_reply", "always"})


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str | None = None


@dataclass(frozen=True)
class FollowUpOverride:
    subject: str | None = None
    text: str | None = None
    html: str | None = None
    skip: bool = False


@dataclass(frozen=True)
class FollowUpStep:
    key: str
    after_days: int
    when: str
    subject: str | None
    text: str
    html: str | None
    require_approval: bool


@dataclass(frozen=True)
class CampaignOptions:
    suppress_replies: bool = True
    reply_window_days: int = 60
    not_before: str | None = None
    stop_on: tuple[str, ...] = ("reply", "bounce")
    allow_duplicates: bool = False
    approval: str = "review"


@dataclass(frozen=True)
class RoutingPolicy:
    mode: str = "auto"
    account: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Message:
    key: str
    recipient: Recipient
    subject: str
    text: str
    html: str | None
    reply_to: str | None
    attachments: tuple[str, ...]
    overrides: dict[str, FollowUpOverride] = field(default_factory=dict)
    source_index: int = 0


@dataclass(frozen=True)
class IgnoredField:
    key: str
    field: str


@dataclass(frozen=True)
class Campaign:
    schema: str
    key: str
    name: str
    producer: dict[str, object]
    routing: RoutingPolicy
    options: CampaignOptions
    messages: tuple[Message, ...]
    followups: tuple[FollowUpStep, ...]
    source_kind: str = "json"
    source_dir: str = ""
    template: str | None = None
    ignored: tuple[IgnoredField, ...] = ()
    duplicates: int = 0
