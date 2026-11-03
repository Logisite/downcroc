from __future__ import annotations

from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import Named, fetch, resolver, text
from downcroc.runtime.paths import resolve


@resolver("batch_id", "batch", "batch_ids")
def batches(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path, state
    rows = fetch(ui, "/api/batches")
    return [
        Named(
            text(row.get("id")),
            text(row.get("name")) or text(row.get("id")),
            _batch_detail(row),
        )
        for row in rows
    ]


def _batch_detail(row: dict) -> str:
    counts = row.get("counts") or {}
    total = sum(int(value or 0) for value in counts.values())
    parts = [text(row.get("state")), text(row.get("kind"))]
    if total:
        parts.append(f"{total:,} jobs")
    if row.get("paused_at"):
        parts.append("paused")
    return "  ".join(part for part in parts if part)


@resolver("job_id", "job", "job_ids")
def jobs(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del state
    if path[:1] == ("failed",):
        rows = fetch(ui, "/api/failed")
        return [
            Named(
                text(row.get("job_id")),
                text(row.get("recipient")) or text(row.get("job_id")),
                f"{text(row.get('code'))}  {text(row.get('batch_id'))}",
            )
            for row in rows
        ]
    rows = fetch(ui, "/api/jobs")
    return [
        Named(
            text(row.get("id")),
            text(row.get("recipient")) or text(row.get("id")),
            _job_detail(row),
        )
        for row in rows
    ]


def _job_detail(row: dict) -> str:
    parts = [text(row.get("state")), text(row.get("batch_id"))]
    return "  ".join(part for part in parts if part)


@resolver("name", path=("template", "show"))
@resolver("name", path=("template", "validate"))
@resolver("path", path=("template", "show"))
@resolver("template")
def templates(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del ui, path, state
    root = resolve().templates
    if not root.is_dir():
        return []
    return [
        Named(child.name, child.name, "template")
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "template.toml").is_file()
    ]
