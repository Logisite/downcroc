from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.transports import AccountTransport


@dataclass(frozen=True)
class DeliveryOutcome:
    status: str
    binding: AccountTransport | None = None
    code: str | None = None
    message: str | None = None
    provider_message_id: str | None = None
    retry_after_s: int | None = None

    @classmethod
    def sent(
        cls, binding: AccountTransport, provider_message_id: str | None
    ) -> DeliveryOutcome:
        return cls(
            "sent",
            binding=binding,
            provider_message_id=provider_message_id,
        )

    @classmethod
    def uncertain(
        cls, binding: AccountTransport, code: str, message: str
    ) -> DeliveryOutcome:
        return cls("uncertain", binding=binding, code=code, message=message)

    @classmethod
    def deferred(
        cls,
        binding: AccountTransport | None,
        code: str,
        message: str,
        retry_after_s: int | None = None,
    ) -> DeliveryOutcome:
        return cls(
            "deferred",
            binding=binding,
            code=code,
            message=message,
            retry_after_s=retry_after_s,
        )

    @classmethod
    def failed(
        cls, binding: AccountTransport, code: str, message: str
    ) -> DeliveryOutcome:
        return cls("failed", binding=binding, code=code, message=message)

    @classmethod
    def reauth(cls, code: str, message: str) -> DeliveryOutcome:
        return cls("reauth", code=code, message=message)
