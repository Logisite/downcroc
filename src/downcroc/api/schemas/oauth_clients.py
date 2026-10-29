from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.transports import OAuthClient


class OAuthClientImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=64)
    payload: str = Field(min_length=2)
    label: str = Field(default="", max_length=120)


class OAuthClientOut(BaseModel):
    id: str
    provider_id: str
    label: str
    client_id: str
    project_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def of(cls, client: OAuthClient) -> OAuthClientOut:
        return cls(
            id=client.id,
            provider_id=client.provider_id,
            label=client.label,
            client_id=client.client_id,
            project_id=client.project_id,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )


class OAuthClientDependentOut(BaseModel):
    binding_id: str
    account_id: str
    address: str
    kind: str
    health: str
