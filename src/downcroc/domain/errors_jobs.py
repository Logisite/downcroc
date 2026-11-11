from __future__ import annotations

from downcroc.domain.errors_base import DomainError


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


class TransportUnavailable(DomainError):
    code = "transport_unavailable"
    status = 503


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


class FollowUpSyncFailed(DomainError):
    code = "followup_sync_failed"
    status = 502


class FollowUpInvalid(DomainError):
    code = "followup_invalid"
    status = 422


class FollowUpStepExists(DomainError):
    code = "followup_step_exists"
    status = 409


class FollowUpStepUsed(DomainError):
    code = "followup_step_used"
    status = 409


class FollowUpNotFound(DomainError):
    code = "followup_not_found"
    status = 404


class FollowUpParentInvalid(DomainError):
    code = "followup_parent_invalid"
    status = 422


class FollowUpOverrideUnknown(DomainError):
    code = "followup_override_unknown"
    status = 422


class FollowUpPayloadGap(DomainError):
    code = "followup_payload_gap"
    status = 422


class FollowUpPayloadExtra(DomainError):
    code = "followup_payload_extra"
    status = 422


class FollowUpPayloadMissing(DomainError):
    code = "followup_payload_missing"
    status = 422


class FollowUpVersionConflict(DomainError):
    code = "followup_version_conflict"
    status = 409


class FollowUpVersionRequired(DomainError):
    code = "followup_version_required"
    status = 409


class FollowUpConfirmRequired(DomainError):
    code = "followup_confirm_required"
    status = 409


class FollowUpInFlight(DomainError):
    code = "followup_in_flight"
    status = 409


class FollowUpSenderUnavailable(DomainError):
    code = "followup_sender_unavailable"
    status = 409


class FollowUpSenderUnresolved(DomainError):
    code = "followup_sender_unresolved"
    status = 409


class FollowUpThreadBroken(DomainError):
    code = "followup_thread_broken"
    status = 409


class SampleAlreadySent(DomainError):
    code = "sample_already_sent"
    status = 409


class InvalidRange(DomainError):
    code = "invalid_range"
    status = 422


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


class BackupFailed(DomainError):
    code = "backup_failed"
    status = 500


class BackupInvalid(DomainError):
    code = "backup_invalid"
    status = 422


class RestoreRefused(DomainError):
    code = "restore_refused"
    status = 409


class RestoreFailed(DomainError):
    code = "restore_failed"
    status = 500


class RestorePending(DomainError):
    code = "restore_pending"
    status = 409


class DaemonRunning(DomainError):
    code = "daemon_running"
    status = 409


class ConfigRejected(DomainError):
    code = "config_rejected"
    status = 422


class ConfirmationRequired(DomainError):
    code = "confirmation_required"
    status = 409


class JobInFlight(DomainError):
    code = "job_in_flight"
    status = 409


class JobNotTerminal(DomainError):
    code = "job_not_terminal"
    status = 409


class JobStateConflict(DomainError):
    code = "job_state_conflict"
    status = 409


class BatchStateConflict(DomainError):
    code = "batch_state_conflict"
    status = 409


class ImportInvalid(DomainError):
    code = "import_invalid"
    status = 422


class ImportChecksumMismatch(DomainError):
    code = "import_checksum_mismatch"
    status = 422


class ImportDuplicate(DomainError):
    code = "import_duplicate"
    status = 409


class ImportJobInFlight(DomainError):
    code = "import_job_in_flight"
    status = 409


class VanillaInvalid(DomainError):
    code = "vanilla_invalid"
    status = 422


class AttachmentMissing(DomainError):
    code = "attachment_missing"
    status = 409


class DuplicateAckRequired(DomainError):
    code = "duplicate_ack_required"
    status = 409

    def __init__(
        self,
        message: str,
        *,
        sent: int,
        total: int,
        recipients: list[str],
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint,
            extra={
                "sent": sent,
                "total": total,
                "recipients": recipients[:10],
            },
        )
        self.sent = sent
        self.total = total
        self.recipients = recipients


class ReassignSameAccount(DomainError):
    code = "reassign_same_account"
    status = 422


class ReassignTargetInvalid(DomainError):
    code = "reassign_target_invalid"
    status = 422


class SenderConflict(DomainError):
    code = "sender_conflict"
    status = 422


class AccountPending(DomainError):
    code = "account_pending"
    status = 409


class AccountArchived(DomainError):
    code = "account_archived"
    status = 409


class BackupNotFound(DomainError):
    code = "backup_not_found"
    status = 404


class TemplateNotFound(DomainError):
    code = "template_not_found"
    status = 404
