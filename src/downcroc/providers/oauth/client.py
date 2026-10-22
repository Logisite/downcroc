from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from downcroc.domain.providers import ProviderSpec

ERROR_CODE = re.compile(r"^[a-z0-9_]{1,64}$")


class OAuthError(Exception):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class OAuthUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scopes: tuple[str, ...]
    token_type: str


def authorization_url(
    spec: ProviderSpec,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    if not spec.oauth_configured:
        raise OAuthError("not_configured")
    params = dict(spec.oauth_extra_params)
    params.update(
        {
            "client_id": spec.oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(spec.oauth_scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{spec.oauth_url(spec.oauth_authorize_url)}?{urlencode(params)}"


def exchange_code(
    spec: ProviderSpec,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    timeout_s: float,
) -> TokenSet:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": spec.oauth_client_id,
        "code_verifier": code_verifier,
    }
    if spec.oauth_client_secret:
        form["client_secret"] = spec.oauth_client_secret
    return _token_request(spec, form, timeout_s)


def refresh(
    spec: ProviderSpec,
    refresh_token: str,
    timeout_s: float,
) -> TokenSet:
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": spec.oauth_client_id,
    }
    if spec.oauth_client_secret:
        form["client_secret"] = spec.oauth_client_secret
    return _token_request(spec, form, timeout_s)


def _token_request(
    spec: ProviderSpec,
    form: dict[str, str],
    timeout_s: float,
) -> TokenSet:
    try:
        response = httpx.post(
            spec.oauth_url(spec.oauth_token_url),
            data=form,
            headers={"Accept": "application/json"},
            timeout=timeout_s,
        )
    except httpx.HTTPError as error:
        raise OAuthUnavailableError from error
    if response.status_code >= 500:
        raise OAuthError("provider_unavailable", status=response.status_code)
    try:
        payload = response.json()
    except ValueError as error:
        raise OAuthError("oauth_bad_response", status=response.status_code) from error
    if not isinstance(payload, dict):
        raise OAuthError("oauth_bad_response", status=response.status_code)
    error_code = payload.get("error")
    if response.status_code >= 400 or error_code:
        code = error_code if isinstance(error_code, str) else "oauth_failed"
        if not ERROR_CODE.fullmatch(code):
            code = "oauth_failed"
        raise OAuthError(code, status=response.status_code)
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError("oauth_bad_response", status=response.status_code)
    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        refresh_token = None
    expires_in = payload.get("expires_in", 0)
    if isinstance(expires_in, bool) or not isinstance(expires_in, int):
        expires_in = 0
    raw_scope = payload.get("scope")
    scopes = tuple(raw_scope.split()) if isinstance(raw_scope, str) else ()
    raw_type = payload.get("token_type")
    token_type = raw_type if isinstance(raw_type, str) else ""
    return TokenSet(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=max(0, expires_in),
        scopes=scopes,
        token_type=token_type,
    )
