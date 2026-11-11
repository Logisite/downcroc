from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.jobs import Job


class ThreadBroken(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ThreadChain:
    root: Job
    anchor: Job
    references: tuple[str, ...]

    @property
    def in_reply_to(self) -> str:
        return self.references[-1]

    @property
    def references_head(self) -> str:
        return self.references[0]


def build_chain(root: Job, anchor: Job, jobs: list[Job]) -> ThreadChain:
    by_id = {job.id: job for job in [root, *jobs]}
    collected: list[Job] = []
    current: Job | None = anchor
    seen: set[str] = set()
    while current is not None:
        if current.id in seen:
            raise ThreadBroken("chain_gap")
        seen.add(current.id)
        if not current.message_id:
            raise ThreadBroken("missing_parent_message_id")
        collected.append(current)
        if current.id == root.id:
            break
        parent_id = current.parent_job_id
        if parent_id is None:
            raise ThreadBroken("parent_not_in_chain")
        found = by_id.get(parent_id)
        if found is None:
            raise ThreadBroken("missing_parent_job")
        current = found
    else:
        raise ThreadBroken("parent_not_in_chain")
    if not collected or collected[-1].id != root.id:
        raise ThreadBroken("missing_parent_message_id")
    references = tuple(job.message_id for job in reversed(collected))
    if not references:
        raise ThreadBroken("references_empty")
    if references[-1] != anchor.message_id:
        raise ThreadBroken("parent_not_in_chain")
    return ThreadChain(root=root, anchor=anchor, references=references)


def subject_has_re(subject: str) -> bool:
    return subject.strip().casefold().startswith("re:")
