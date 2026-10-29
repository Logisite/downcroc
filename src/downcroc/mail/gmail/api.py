from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from downcroc.domain.accounts import Account
from downcroc.domain.providers import ProviderSpec
from downcroc.runtime.clock import parse_utc, utc_now

SEND_PATH = "/gmail/v1/users/me/messages/send"
PROFILE_PATH = "/gmail/v1/users/me/profile"
RATE_REASONS = frozenset(
    {
        "rateLimitExceeded",
        "userRateLimitExceeded",
        "RATE_LIMIT_EXCEEDED",
        "QUOTA_EXCEEDED",
    }
)
DISABLED_REASONS = frozenset({"accessNotConfigured", "SERVICE_DISABLED"})


@dataclass(frozen=True)
class GmailSendResult:
    provider_message_id: str
    accepted_ms: int


@dataclass(frozen=True)
class GmailProfile:
    address: str
    messages_total: int
    threads_total: int
    history_id: str | None


class GmailApiFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        transient: bool = False,
        auth: bool = False,
        quota: bool = False,
        uncertain: bool = False,
        retry_after_s: int | None = None,
        project_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.transient = transient
        self.auth = auth
        self.quota = quota
        self.uncertain = uncertain
        self.retry_after_s = retry_after_s
        self.project_id = project_id


def send(
    spec: ProviderSpec,
    account: Account,
    access_token: str,
    wire: bytes,
    *,
    timeout_s: float,
    project_id: str | None = None,
) -> GmailSendResult:
    if not spec.api_configured:
        raise GmailApiFailure(
            "gmail_api_not_configured",
            "the provider has no gmail api base url",
        )
    if len(wire) > spec.attachment_max_bytes:
        raise GmailApiFailure(
            "gmail_api_too_large",
            "the message exceeds the provider size limit",
        )
    body = {"raw": base64.urlsafe_b64encode(wire).decode("ascii")}
    started = time.monotonic()
    response = _request(
        spec,
        "POST",
        SEND_PATH,
        access_token,
        timeout_s,
        json=body,
        project_id=project_id,
    )
    accepted_ms = round((time.monotonic() - started) * 1000)
    message_id = _message_id(response)
    if message_id is None:
        raise GmailApiFailure(
            "gmail_api_bad_response",
            "the api accepted the request without a message id",
            uncertain=True,
            project_id=project_id,
        )
    return GmailSendResult(provider_message_id=message_id, accepted_ms=accepted_ms)


def profile(
    spec: ProviderSpec,
    access_token: str,
    *,
    timeout_s: float,
    project_id: str | None = None,
) -> GmailProfile:
    if not spec.api_configured:
        raise GmailApiFailure(
            "gmail_api_not_configured",
            "the provider has no gmail api base url",
        )
    response = _request(
        spec,
        "GET",
        PROFILE_PATH,
        access_token,
        timeout_s,
        project_id=project_id,
    )
    payload = _json(response, project_id)
    address = payload.get("emailAddress")
    if not isinstance(address, str) or not address:
        raise GmailApiFailure(
            "gmail_api_bad_response",
            "the profile response has no email address",
            project_id=project_id,
        )
    return GmailProfile(
        address=address,
        messages_total=_count(payload.get("messagesTotal")),
        threads_total=_count(payload.get("threadsTotal")),
        history_id=_text(payload.get("historyId")),
    )


def _request(
    spec: ProviderSpec,
    method: str,
    path: str,
    access_token: str,
    timeout_s: float,
    *,
    json: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> httpx.Response:
    url = f"{spec.api_base_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    if json is not None:
        headers["Content-Type"] = "application/json"
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=json,
            timeout=timeout_s,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        raise GmailApiFailure(
            "gmail_api_unavailable",
            "the gmail api could not be reached",
            transient=True,
            project_id=project_id,
        ) from error
    except httpx.HTTPError as error:
        raise GmailApiFailure(
            "gmail_api_unavailable",
            "the gmail api request did not complete",
            transient=True,
            uncertain=True,
            project_id=project_id,
        ) from error
    if response.status_code >= 400:
        raise _failure(response, project_id)
    return response


def _failure(response: httpx.Response, project_id: str | None) -> GmailApiFailure:
    payload = _safe_json(response)
    reasons = _reasons(payload)
    message = _error_message(payload) or f"gmail api returned {response.status_code}"
    status = response.status_code
    if status == 401:
        return GmailApiFailure(
            "gmail_api_unauthorized",
            message,
            auth=True,
            project_id=project_id,
        )
    if status == 403 and reasons & DISABLED_REASONS:
        return GmailApiFailure(
            "gmail_api_disabled",
            message,
            project_id=_project(payload) or project_id,
        )
    if status == 403 and reasons & RATE_REASONS:
        return GmailApiFailure(
            "gmail_api_quota",
            message,
            quota=True,
            retry_after_s=_retry_after(response),
            project_id=project_id,
        )
    if status == 429:
        return GmailApiFailure(
            "gmail_api_quota",
            message,
            quota=True,
            retry_after_s=_retry_after(response),
            project_id=project_id,
        )
    if status >= 500:
        return GmailApiFailure(
            "gmail_api_unavailable",
            message,
            transient=True,
            uncertain=True,
            project_id=project_id,
        )
    if status == 403:
        return GmailApiFailure(
            "gmail_api_forbidden",
            message,
            project_id=project_id,
        )
    return GmailApiFailure(
        "gmail_api_failed",
        message,
        project_id=project_id,
    )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json(response: httpx.Response, project_id: str | None) -> dict[str, Any]:
    payload = _safe_json(response)
    if not payload:
        raise GmailApiFailure(
            "gmail_api_bad_response",
            "the gmail api returned an empty response",
            project_id=project_id,
        )
    return payload


def _reasons(payload: dict[str, Any]) -> set[str]:
    error = payload.get("error")
    if not isinstance(error, dict):
        return set()
    reasons: set[str] = set()
    raw = error.get("errors")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("reason"), str):
                reasons.add(item["reason"])
    status = error.get("status")
    if isinstance(status, str):
        reasons.add(status)
    details = error.get("details")
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and isinstance(item.get("reason"), str):
                reasons.add(item["reason"])
    return reasons


def _error_message(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"][:500]
    return None


def _project(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    details = error.get("details")
    if not isinstance(details, list):
        return None
    for item in details:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        consumer = metadata.get("consumer")
        if isinstance(consumer, str) and consumer.startswith("projects/"):
            return consumer.split("/", 1)[1]
    return None


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0, int(value.strip()))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, int((when - parse_utc(utc_now())).total_seconds()))


def _message_id(response: httpx.Response) -> str | None:
    payload = _safe_json(response)
    value = payload.get("id")
    return value if isinstance(value, str) and value else None


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
