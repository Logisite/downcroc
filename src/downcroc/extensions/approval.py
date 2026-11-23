from __future__ import annotations

import hashlib
import json

from downcroc.core.vault.service import VaultService
from downcroc.extensions.manifest import Manifest
from downcroc.extensions.store import ExtensionStore
from downcroc.runtime.logging.setup import EventLogger


class ApprovalService:
    def __init__(
        self, store: ExtensionStore, vault: VaultService, log: EventLogger
    ) -> None:
        self._store = store
        self._vault = vault
        self._log = log

    def approve(self, manifest: Manifest, password: str) -> dict[str, str]:
        if self._vault.status().state == "locked":
            self._vault.unlock(password)
        elif not self._vault.verify(password):
            raise ValueError("invalid vault password")
        record = {
            "manifest_digest": manifest_digest(manifest),
            "capability_digest": capability_digest(manifest),
            "tier": manifest.tier,
        }
        self._store.save_approval(manifest.id, **record)
        self._log.info(
            "extension.approved",
            extension=manifest.id,
            tier=manifest.tier,
            manifest_digest=record["manifest_digest"][:16],
        )
        return self._store.approval(manifest.id) or record

    def revoke(self, extension: str) -> None:
        self._store.delete_approval(extension)
        self._log.info("extension.revoked", extension=extension)

    def status(self, manifest: Manifest) -> dict[str, object]:
        record = self._store.approval(manifest.id)
        approved = bool(
            record
            and record["manifest_digest"] == manifest_digest(manifest)
            and record["capability_digest"] == capability_digest(manifest)
        )
        return {
            "extension": manifest.id,
            "tier": manifest.tier,
            "approved": approved,
            "approved_at": record["approved_at"] if approved else None,
        }

    def is_approved(self, manifest: Manifest) -> bool:
        return bool(self.status(manifest)["approved"])


def manifest_digest(manifest: Manifest) -> str:
    if manifest.artifact_sha256:
        return manifest.artifact_sha256
    if manifest.source.is_file():
        return hashlib.sha256(manifest.source.read_bytes()).hexdigest()
    return hashlib.sha256(manifest.id.encode()).hexdigest()


def capability_digest(manifest: Manifest) -> str:
    payload = json.dumps(
        {"tier": manifest.tier, "capabilities": sorted(manifest.capabilities)},
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
