from __future__ import annotations

from downcroc.domain.errors_base import DomainError, ProviderConfigError
from downcroc.domain.errors_jobs import (
    AccountArchived,
    AccountPending,
    AttachmentMissing,
    AttachmentNotFound,
    BackupFailed,
    BackupInvalid,
    BackupNotFound,
    BatchInvalid,
    BatchNotAwaitingApproval,
    BatchNotFound,
    BatchStateConflict,
    ConfigRejected,
    ConfirmationRequired,
    ContentCorrupt,
    ContentMissing,
    DaemonRunning,
    DuplicateAckRequired,
    FailureNotFound,
    FollowUpConfirmRequired,
    FollowUpInFlight,
    FollowUpInvalid,
    FollowUpNotFound,
    FollowUpOverrideUnknown,
    FollowUpParentInvalid,
    FollowUpPayloadExtra,
    FollowUpPayloadGap,
    FollowUpPayloadMissing,
    FollowUpSenderUnavailable,
    FollowUpSenderUnresolved,
    FollowUpStepExists,
    FollowUpStepUsed,
    FollowUpSyncFailed,
    FollowUpThreadBroken,
    FollowUpVersionConflict,
    FollowUpVersionRequired,
    ImportChecksumMismatch,
    ImportDuplicate,
    ImportInvalid,
    ImportJobInFlight,
    InputUnreadable,
    InvalidJob,
    InvalidRange,
    JobInFlight,
    JobNotFailed,
    JobNotFound,
    JobNotSendable,
    JobNotTerminal,
    JobStateConflict,
    MessageNotFound,
    ReassignSameAccount,
    ReassignTargetInvalid,
    RestoreFailed,
    RestorePending,
    RestoreRefused,
    SampleAlreadySent,
    SenderConflict,
    SmtpUnavailable,
    TemplateNotFound,
    ThreadNotFound,
    TransportUnavailable,
    UnsupportedSchema,
    VanillaInvalid,
)

__all__ = (
    "AccountArchived",
    "AccountExists",
    "AccountInUse",
    "AccountNeedsReauth",
    "AccountNotFound",
    "AccountPending",
    "AccountUnavailable",
    "AttachmentMissing",
    "AttachmentNotFound",
    "AttemptNotFound",
    "AttemptNotPending",
    "AttemptPending",
    "BackupFailed",
    "BackupInvalid",
    "BackupNotFound",
    "BatchInvalid",
    "BatchNotAwaitingApproval",
    "BatchNotFound",
    "BatchStateConflict",
    "ConfigRejected",
    "ConfirmationRequired",
    "ContentCorrupt",
    "ContentMissing",
    "CredentialMissing",
    "DaemonRunning",
    "DomainError",
    "DuplicateAckRequired",
    "FailureNotFound",
    "FollowUpConfirmRequired",
    "FollowUpInFlight",
    "FollowUpInvalid",
    "FollowUpNotFound",
    "FollowUpOverrideUnknown",
    "FollowUpParentInvalid",
    "FollowUpPayloadExtra",
    "FollowUpPayloadGap",
    "FollowUpPayloadMissing",
    "FollowUpSenderUnavailable",
    "FollowUpSenderUnresolved",
    "FollowUpStepExists",
    "FollowUpStepUsed",
    "FollowUpSyncFailed",
    "FollowUpThreadBroken",
    "FollowUpVersionConflict",
    "FollowUpVersionRequired",
    "ImapAuthFailed",
    "ImapTlsFailed",
    "ImapUnreachable",
    "ImportChecksumMismatch",
    "ImportDuplicate",
    "ImportInvalid",
    "ImportJobInFlight",
    "InputUnreadable",
    "InvalidAccount",
    "InvalidJob",
    "InvalidRange",
    "JobInFlight",
    "JobNotFailed",
    "JobNotFound",
    "JobNotSendable",
    "JobNotTerminal",
    "JobStateConflict",
    "MessageNotFound",
    "OAuthClientInUse",
    "OAuthClientInvalid",
    "OAuthClientNotFound",
    "OAuthFailed",
    "OAuthListenerFailed",
    "OAuthNotConfigured",
    "OAuthUnavailable",
    "PauseDurationInvalid",
    "ProviderAuthMismatch",
    "ProviderConfigError",
    "ProviderInUse",
    "ProviderInvalid",
    "ProviderNotConfigured",
    "ProviderUnknown",
    "ReassignSameAccount",
    "ReassignTargetInvalid",
    "RestoreFailed",
    "RestorePending",
    "RestoreRefused",
    "SampleAlreadySent",
    "SenderConflict",
    "SendingPaused",
    "SmtpUnavailable",
    "TemplateNotFound",
    "ThreadNotFound",
    "TransportUnavailable",
    "UnsupportedSchema",
    "VanillaInvalid",
    "VaultAlreadyUnlocked",
    "VaultBadPassword",
    "VaultCorrupt",
    "VaultExists",
    "VaultLocked",
    "VaultSecretMissing",
    "VaultThrottled",
    "VaultUnavailable",
    "VaultWriteFailed",
)


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


class VaultExists(DomainError):
    code = "vault_exists"
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


class ProviderInvalid(DomainError):
    code = "provider_invalid"
    status = 400


class ProviderInUse(DomainError):
    code = "provider_in_use"
    status = 409


class ProviderUnknown(DomainError):
    code = "provider_unknown"
    status = 409


class OAuthClientNotFound(DomainError):
    code = "oauth_client_not_found"
    status = 404


class OAuthClientInvalid(DomainError):
    code = "oauth_client_invalid"
    status = 422


class OAuthClientInUse(DomainError):
    code = "oauth_client_in_use"
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


class SendingPaused(DomainError):
    code = "sending_paused"
    status = 409


class PauseDurationInvalid(DomainError):
    code = "pause_duration_invalid"
    status = 422
