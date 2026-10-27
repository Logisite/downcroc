from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.core.vault_service import VaultStatus


class VaultInit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=1024)


class VaultUnlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=1024)


class VaultAccount(BaseModel):
    id: str
    credential_present: bool


class VaultOut(BaseModel):
    state: str
    path: str
    unlocked_at: str | None
    attempts_left: int
    retry_after_s: float
    accounts: list[VaultAccount]

    @classmethod
    def of(cls, status: VaultStatus, accounts: list[VaultAccount]) -> VaultOut:
        return cls(
            state=status.state,
            path=status.path,
            unlocked_at=status.unlocked_at,
            attempts_left=status.attempts_left,
            retry_after_s=status.retry_after_s,
            accounts=accounts,
        )
