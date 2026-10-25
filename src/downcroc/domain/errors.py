from __future__ import annotations

from pathlib import Path


class DomainError(Exception):
    code = "domain_error"
    status = 400

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        fields: dict[str, str] | None = None,
        details: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.fields = fields
        self.details = details


class ProviderConfigError(Exception):
    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.field = field


class AccountNotFound(DomainError):
    code = "account_not_found"
    status = 404


class AccountExists(DomainError):
    code = "account_exists"
    status = 409


class AccountInUse(DomainError):
    code = "account_in_use"
    status = 409


class AccountUnavailable(DomainError):
    code = "account_unavailable"
    status = 409


class InvalidAccount(DomainError):
    code = "invalid_account"
    status = 422


class VaultLocked(DomainError):
    code = "vault_locked"
    status = 423


class VaultBadPassword(DomainError):
    code = "vault_bad_password"
    status = 401


class VaultThrottled(DomainError):
    code = "vault_throttled"
    status = 429


class VaultCorrupt(DomainError):
    code = "vault_corrupt"
    status = 409


class VaultAlreadyUnlocked(DomainError):
    code = "vault_already_unlocked"
    status = 409


class VaultWriteFailed(DomainError):
    code = "vault_write_failed"
    status = 500


class VaultUnavailable(DomainError):
    code = "vault_unavailable"
    status = 500


class VaultSecretMissing(DomainError):
    code = "vault_secret_missing"
    status = 404


class ProviderUnknown(DomainError):
    code = "provider_unknown"
    status = 409


class ProviderNotConfigured(DomainError):
    code = "provider_not_configured"
    status = 409


class ProviderAuthMismatch(DomainError):
    code = "provider_auth_mismatch"
    status = 422


class AttemptNotFound(DomainError):
    code = "attempt_not_found"
    status = 404


class AttemptNotPending(DomainError):
    code = "attempt_not_pending"
    status = 409


class AttemptPending(DomainError):
    code = "attempt_pending"
    status = 409


class OAuthNotConfigured(DomainError):
    code = "oauth_not_configured"
    status = 409


class OAuthListenerFailed(DomainError):
    code = "oauth_listener_failed"
    status = 500


class OAuthFailed(DomainError):
    code = "oauth_failed"
    status = 502


class OAuthUnavailable(DomainError):
    code = "oauth_unavailable"
    status = 502


class ImapAuthFailed(DomainError):
    code = "imap_auth_failed"
    status = 401


class ImapUnreachable(DomainError):
    code = "imap_unreachable"
    status = 502


class ImapTlsFailed(DomainError):
    code = "imap_tls_failed"
    status = 502


class CredentialMissing(DomainError):
    code = "credential_missing"
    status = 409


class AccountNeedsReauth(DomainError):
    code = "account_needs_reauth"
    status = 409


class JobNotFound(DomainError):
    code = "job_not_found"
    status = 404


class JobNotSendable(DomainError):
    code = "job_not_sendable"
    status = 409


class InvalidJob(DomainError):
    code = "invalid_job"
    status = 422


class SmtpUnavailable(DomainError):
    code = "smtp_unavailable"
    status = 502


class MessageNotFound(DomainError):
    code = "message_not_found"
    status = 404


class ThreadNotFound(DomainError):
    code = "thread_not_found"
    status = 404


class AttachmentNotFound(DomainError):
    code = "attachment_not_found"
    status = 404


class ContentMissing(DomainError):
    code = "content_missing"
    status = 410


class ContentCorrupt(DomainError):
    code = "content_corrupt"
    status = 500


class BatchNotFound(DomainError):
    code = "batch_not_found"
    status = 404


class BatchInvalid(DomainError):
    code = "batch_invalid"
    status = 422


class BatchNotAwaitingApproval(DomainError):
    code = "batch_not_awaiting_approval"
    status = 409


class SampleAlreadySent(DomainError):
    code = "sample_already_sent"
    status = 409


class UnsupportedSchema(DomainError):
    code = "unsupported_schema"
    status = 422


class InputUnreadable(DomainError):
    code = "input_unreadable"
    status = 422


class FailureNotFound(DomainError):
    code = "failure_not_found"
    status = 404


class JobNotFailed(DomainError):
    code = "job_not_failed"
    status = 409
