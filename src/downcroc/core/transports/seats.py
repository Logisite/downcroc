from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.transports import TransportKind


@dataclass(frozen=True)
class SlotEntry:
    """One eligible mailbox as the slot planner sees it."""

    account_id: str
    password: bool
    pinned: bool
    remaining: int
    turn: int
    jitter: float
    has_smtp: bool
    has_api: bool
    smtp_ready: bool


@dataclass(frozen=True)
class SlotPlan:
    """The active SMTP rotation plus everything waiting for a turn.

    ``active`` is ordered: pinned accounts first, then password accounts, then
    OAuth accounts. The order is also the rotation order.
    """

    seats: int
    active: tuple[str, ...]
    queue: tuple[str, ...]
    waiting: tuple[str, ...]
    pinned_overflow: int = 0
    password_active: tuple[str, ...] = ()
    oauth_active: tuple[str, ...] = ()

    @property
    def active_set(self) -> frozenset[str]:
        return frozenset(self.active)

    def kinds_for(
        self,
        account_id: str,
        *,
        has_smtp: bool,
        has_api: bool,
    ) -> frozenset[TransportKind]:
        """The only send mechanisms an account may use under this plan.

        A seated account is SMTP-only. An unseated OAuth account is API-only.
        An unseated password account has no usable mechanism and waits.
        """
        if account_id in self.active_set and has_smtp:
            return frozenset({TransportKind.SMTP})
        if account_id not in self.active_set and has_api:
            return frozenset({TransportKind.GMAIL_API})
        return frozenset()

    def status_for(
        self,
        account_id: str,
        *,
        has_smtp: bool,
        has_api: bool,
    ) -> str:
        if account_id in self.active_set and has_smtp:
            return "active"
        if has_api:
            return "api_only"
        if has_smtp:
            return "waiting"
        return "none"


def choose_slots(entries: list[SlotEntry], seats: int) -> SlotPlan:
    """Choose the active SMTP rotation from the live queue.

    Pinned accounts always keep a turn because their job cannot move. The
    configured width applies to the remaining auto rotation.
    """
    width = max(1, min(int(seats), 10))
    eligible = [
        entry
        for entry in entries
        if entry.has_smtp and entry.smtp_ready and entry.remaining > 0
    ]
    ordered = sorted(
        eligible,
        key=lambda entry: (
            0 if entry.pinned else 1,
            0 if entry.password else 1,
            entry.turn,
            entry.jitter,
            entry.account_id,
        ),
    )
    pinned = [entry for entry in ordered if entry.pinned]
    auto = [entry for entry in ordered if not entry.pinned]
    active = pinned + auto[:width]
    return SlotPlan(
        seats=width,
        active=tuple(entry.account_id for entry in active),
        queue=tuple(entry.account_id for entry in ordered),
        waiting=tuple(entry.account_id for entry in auto[width:]),
        pinned_overflow=max(0, len(pinned) - width),
        password_active=tuple(
            entry.account_id for entry in active if entry.password
        ),
        oauth_active=tuple(
            entry.account_id for entry in active if not entry.password
        ),
    )
