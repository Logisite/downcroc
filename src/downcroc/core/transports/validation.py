from __future__ import annotations

from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import OAuthClientNotFound
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.transports import AccountTransport, OAuthClient, TransportKind
from downcroc.mail.gmail import api as gmail_api
from downcroc.store.repositories.transports import TransportInvalid


def validate_binding(
    kind: TransportKind,
    spec: ProviderSpec,
    max_concurrency: int | None,
    rate_per_min: int | None,
) -> None:
    if kind is TransportKind.SMTP:
        if not spec.smtp_host or not spec.smtp_port:
            raise TransportInvalid(
                "the provider has no smtp host",
                hint="declare smtp_host and smtp_port first",
            )
        if rate_per_min is not None:
            raise TransportInvalid("rate_per_min applies to gmail_api bindings")
    if kind is TransportKind.GMAIL_API:
        if spec.id != "gmail":
            raise TransportInvalid(
                "gmail_api bindings are only supported for gmail",
                hint="use an smtp binding for this provider",
            )
        if spec.auth_kind is not AuthKind.OAUTH2:
            raise TransportInvalid("gmail_api requires an oauth2 provider")
    if max_concurrency is not None and max_concurrency < 1:
        raise TransportInvalid("max_concurrency must be at least 1")
    if rate_per_min is not None and rate_per_min < 1:
        raise TransportInvalid("rate_per_min must be at least 1")


def resolve_client_id(
    clients: OAuthClientService,
    account: Account,
    client_id: str | None,
) -> str:
    resolved = clients.resolve_id(account.provider, client_id)
    if resolved is None:
        raise TransportInvalid(
            "the provider has no oauth client",
            hint="import one with downcroc provider credentials set gmail",
        )
    return resolved


def client_of(
    clients: OAuthClientService,
    binding: AccountTransport,
) -> OAuthClient | None:
    if binding.oauth_client_id is None:
        return None
    try:
        return clients.get(binding.oauth_client_id)
    except OAuthClientNotFound:
        return None


def api_message(
    error: gmail_api.GmailApiFailure,
    project_id: str | None,
) -> str:
    project = error.project_id or project_id
    if error.code == "gmail_api_disabled" and project:
        return (
            "the gmail api is disabled for the project; enable it at "
            "https://console.cloud.google.com/apis/library/"
            f"gmail.googleapis.com?project={project}"
        )
    return error.message
