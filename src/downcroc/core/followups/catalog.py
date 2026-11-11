from __future__ import annotations

from collections.abc import Callable

from downcroc.core.followups.payload import PayloadDocument
from downcroc.core.followups.planner import PlannedStep
from downcroc.core.followups.snapshot import ParentDeclaration, read_parent
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.domain.batches import Batch
from downcroc.domain.campaign import FollowUpOverride
from downcroc.domain.followups import FollowUpDeclaration
from downcroc.store.content import ContentStore


class SnapshotCache:
    def __init__(self, content: ContentStore, limits: IntakeLimits) -> None:
        self._content = content
        self._limits = limits
        self._cache: dict[str, ParentDeclaration] = {}

    def get(self, batch: Batch) -> ParentDeclaration:
        cached = self._cache.get(batch.source_ref)
        if cached is None:
            cached = read_parent(batch, self._content, self._limits)
            self._cache[batch.source_ref] = cached
        return cached

    def set_limits(self, limits: IntakeLimits) -> None:
        self._limits = limits
        self.clear()

    def clear(self) -> None:
        self._cache.clear()


def snapshot_steps(declaration: ParentDeclaration) -> list[PlannedStep]:
    steps: list[PlannedStep] = []
    for step in declaration.followups:
        overrides = _snapshot_overrides(declaration, step.key)
        steps.append(PlannedStep(step=step, overrides=overrides))
    return steps


def declaration_steps(
    declarations: list[FollowUpDeclaration],
    payload_loader: Callable[[FollowUpDeclaration], PayloadDocument],
) -> list[PlannedStep]:
    steps: list[PlannedStep] = []
    for declaration in declarations:
        payload = (
            payload_loader(declaration) if declaration.content_ref is not None else None
        )
        steps.append(
            PlannedStep(
                step=declaration.step(),
                overrides=declaration.overrides,
                payload=payload,
                declaration=declaration,
            )
        )
    return steps


def merge_steps(
    automatic: list[PlannedStep],
    retroactive: list[PlannedStep],
) -> list[PlannedStep]:
    keys = {item.step.key for item in automatic}
    merged = list(automatic)
    for item in retroactive:
        if item.step.key in keys:
            continue
        keys.add(item.step.key)
        merged.append(item)
    return merged


def _snapshot_overrides(
    declaration: ParentDeclaration, step_key: str
) -> dict[str, FollowUpOverride]:
    overrides: dict[str, FollowUpOverride] = {}
    for source_key, steps in declaration.overrides.items():
        override = steps.get(step_key)
        if override is not None:
            overrides[source_key] = override
    return overrides
