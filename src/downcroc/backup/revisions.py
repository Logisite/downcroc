from __future__ import annotations

from downcroc.domain.errors import RestoreRefused
from downcroc.store.db.migrate import current_head, known_revisions


def check_revision(revision: str) -> None:
    if revision in known_revisions():
        return
    head = current_head() or "none"
    raise RestoreRefused(
        f"bundle schema revision {revision} is not known to this build",
        fields={
            "revision": revision,
            "current": head,
            "reason": "unknown schema revision",
        },
    )
