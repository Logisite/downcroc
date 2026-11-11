from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

from downcroc.core.events import EventBus
from downcroc.core.vault import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNotFound,
    OAuthClientInUse,
    OAuthClientInvalid,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.secrets import client_secret_key
from downcroc.domain.transports import AccountTransport, OAuthClient
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.oauth_clients import OAuthClientRepo
from downcroc.store.repositories.transports import TransportRepo

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class ClientJSON:
    kind: str
    client_id: str
    client_secret: str
    project_id: str | None
    auth_uri: str
    token_uri: str
    redirect_uris: tuple[str, ...]


def parse_client_json(text: str) -> ClientJSON:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise OAuthClientInvalid(
            "the client file is not valid JSON",
            hint="download the Desktop OAuth client JSON from Google Cloud",
        ) from error
    if not isinstance(data, dict):
        raise OAuthClientInvalid("the client file must hold a JSON object")
    kinds = [key for key in ("installed", "web") if key in data]
    if len(kinds) != 1:
        raise OAuthClientInvalid(
            "the client file is not a Google OAuth client",
            hint="download a Desktop app client JSON",
        )
    kind = kinds[0]
    inner = data.get(kind)
    if not isinstance(inner, dict):
        raise OAuthClientInvalid("the client entry must be an object")
    client_id = _text(inner.get("client_id"))
    client_secret = _text(inner.get("client_secret"))
    if not client_id:
        raise OAuthClientInvalid("the client file has no client_id")
    if not client_secret:
        raise OAuthClientInvalid("the client file has no client_secret")
    redirects = inner.get("redirect_uris")
    redirect_uris = (
        tuple(item for item in redirects if isinstance(item, str) and item)
        if isinstance(redirects, list)
        else ()
    )
    if kind == "web" and not any(_loopback(item) for item in redirect_uris):
        raise OAuthClientInvalid(
            "the web client has no loopback redirect",
            hint="create a Desktop app client instead of a Web client",
        )
    return ClientJSON(
        kind=kind,
        client_id=client_id,
        client_secret=client_secret,
        project_id=_text(inner.get("project_id")) or None,
        auth_uri=_text(inner.get("auth_uri")),
        token_uri=_text(inner.get("token_uri")),
        redirect_uris=redirect_uris,
    )


class OAuthClientService:
    def __init__(
        self,
        clients: OAuthClientRepo,
        transports: TransportRepo,
        accounts: AccountRepo,
        vault: VaultService,
        registry: ProviderRegistry,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._clients = clients
        self._transports = transports
        self._accounts = accounts
        self._vault = vault
        self._registry = registry
        self._bus = bus
        self._log = log

    def import_json(
        self,
        provider_id: str,
        text: str,
        label: str = "",
    ) -> OAuthClient:
        spec = self._registry.get(provider_id)
        if spec.auth_kind is not AuthKind.OAUTH2:
            raise OAuthClientInvalid(
                "the provider does not use an oauth client",
                fields={"provider": provider_id},
            )
        self._vault.ensure_unlocked()
        parsed = parse_client_json(text)
        existing = self._clients.find(provider_id, parsed.client_id)
        if existing is not None:
            return self._replace(existing, parsed, text, label)
        now = utc_now()
        client_id = new_id("oac")
        client = OAuthClient(
            id=client_id,
            provider_id=provider_id,
            label=label or parsed.project_id or parsed.client_id[:12],
            client_id=parsed.client_id,
            project_id=parsed.project_id,
            secret_ref=client_secret_key(client_id),
            created_at=now,
            updated_at=now,
        )
        self._store(client.secret_ref, text)
        created = self._clients.create(client)
        self._publish(
            "oauth.client_created",
            created,
            project_id=created.project_id,
        )
        return created

    def list(self, provider_id: str | None = None) -> list[OAuthClient]:
        return self._clients.list(provider_id)

    def get(self, client_id: str) -> OAuthClient:
        return self._clients.get(client_id)

    def dependents(self, client_id: str) -> list[AccountTransport]:
        self.get(client_id)
        return self._clients.dependents(client_id)

    def dependent_rows(self, client_id: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for binding in self.dependents(client_id):
            try:
                account = self._accounts.get(binding.account_id)
                address = account.address
            except AccountNotFound:
                address = ""
            rows.append(
                {
                    "binding_id": binding.id,
                    "account_id": binding.account_id,
                    "address": address,
                    "kind": binding.kind.value,
                    "health": binding.health.value,
                }
            )
        return rows

    def default_for(self, provider_id: str) -> OAuthClient | None:
        found = self._clients.list(provider_id)
        return found[0] if len(found) == 1 else None

    def resolve_id(self, provider_id: str, client_id: str | None) -> str | None:
        if client_id:
            client = self.get(client_id)
            if client.provider_id != provider_id:
                raise OAuthClientInvalid(
                    "the client belongs to another provider",
                    fields={"client": client_id, "provider": provider_id},
                )
            return client.id
        default = self.default_for(provider_id)
        return default.id if default is not None else None

    def spec_for(self, provider_id: str, client_id: str | None = None) -> ProviderSpec:
        spec = self._registry.get(provider_id)
        resolved = self.resolve_id(provider_id, client_id)
        return self.overlay(spec, resolved)

    def spec_for_account(self, account: Account) -> ProviderSpec:
        spec = self._registry.get(account.provider)
        client_id = self.account_client(account)
        return self.overlay(spec, client_id)

    def overlay(self, spec: ProviderSpec, client_id: str | None) -> ProviderSpec:
        if not client_id:
            return spec
        parsed = self.payload(self.get(client_id))
        return replace(
            spec,
            oauth_client_id=parsed.client_id,
            oauth_client_secret=parsed.client_secret,
            oauth_authorize_url=parsed.auth_uri or spec.oauth_authorize_url,
            oauth_token_url=parsed.token_uri or spec.oauth_token_url,
        )

    def payload(self, client: OAuthClient) -> ClientJSON:
        try:
            secret = self._vault.get_secret(client.secret_ref)
        except VaultLocked:
            raise
        except VaultSecretMissing as error:
            raise OAuthClientInvalid(
                "the stored client secret is missing",
                hint="import the client JSON again",
                fields={"client": client.id},
            ) from error
        except Exception as error:
            raise OAuthClientInvalid(
                "the stored client secret could not be read",
                hint="import the client JSON again",
                fields={"client": client.id},
            ) from error
        return parse_client_json(secret.value)

    def revoke(self, client_id: str) -> OAuthClient:
        client = self.get(client_id)
        dependents = self._clients.dependents(client_id)
        for binding in dependents:
            self._transports.update(
                binding.id,
                {
                    "health": "needs_reauth",
                    "last_error_code": "oauth_client_revoked",
                    "last_error_message": "the oauth client was revoked",
                    "cooldown_until": None,
                    "updated_at": utc_now(),
                },
            )
        self._publish("oauth.client_revoked", client, dependents=len(dependents))
        return client

    def delete(self, client_id: str, *, force: bool = False) -> OAuthClient:
        client = self.get(client_id)
        dependents = self._clients.dependents(client_id)
        if dependents and not force:
            raise OAuthClientInUse(
                "bindings still use this client",
                hint="revoke it, or pass force to move them to reauth",
                details=[
                    {"binding_id": item.id, "account_id": item.account_id}
                    for item in dependents
                ],
            )
        if dependents:
            self.revoke(client_id)
        self._vault.delete_secret(client.secret_ref)
        removed = self._clients.delete(client_id)
        self._publish("oauth.client_deleted", removed, dependents=len(dependents))
        return removed

    def account_client(self, account: Account) -> str | None:
        for binding in self._transports.list_for_account(account.id):
            if binding.oauth_client_id:
                return binding.oauth_client_id
        default = self.default_for(account.provider)
        return default.id if default is not None else None

    def _replace(
        self,
        existing: OAuthClient,
        parsed: ClientJSON,
        text: str,
        label: str,
    ) -> OAuthClient:
        self._store(existing.secret_ref, text)
        changes: dict[str, object] = {
            "project_id": parsed.project_id,
            "updated_at": utc_now(),
        }
        if label:
            changes["label"] = label
        updated = self._clients.update(existing.id, changes)
        dependents = len(self._clients.dependents(existing.id))
        self._publish(
            "oauth.client_replaced",
            updated,
            dependents=dependents,
        )
        return updated

    def _store(self, key: str, text: str) -> None:
        self._vault.set_secret(key, text)

    def _publish(self, event: str, client: OAuthClient, **fields: object) -> None:
        payload: dict[str, object] = {
            "client": client.id,
            "provider": client.provider_id,
        }
        payload.update(fields)
        self._bus.publish(event, payload)
        self._log.info(event, **payload)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _loopback(uri: str) -> bool:
    parsed = urlparse(uri)
    return parsed.scheme == "http" and (parsed.hostname or "") in LOOPBACK_HOSTS


__all__ = ["ClientJSON", "OAuthClientService", "parse_client_json"]
