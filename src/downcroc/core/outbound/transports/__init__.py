from __future__ import annotations

from downcroc.core.outbound.transports.gmail import GmailDelivery
from downcroc.core.outbound.transports.outcome import DeliveryOutcome
from downcroc.core.outbound.transports.selection import TransportDelivery
from downcroc.core.outbound.transports.smtp import SmtpDelivery

__all__ = [
    "DeliveryOutcome",
    "GmailDelivery",
    "SmtpDelivery",
    "TransportDelivery",
]
