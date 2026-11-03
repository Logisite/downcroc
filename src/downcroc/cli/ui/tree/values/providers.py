from __future__ import annotations

from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree.state import LeafState
from downcroc.cli.ui.tree.values.registry import Named, fetch, resolver, text


@resolver("provider_id", "provider")
def providers(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path, state
    rows = fetch(ui, "/api/providers")
    return [
        Named(
            text(row.get("id")),
            text(row.get("label")) or text(row.get("id")),
            _provider_detail(row),
        )
        for row in rows
    ]


def _provider_detail(row: dict) -> str:
    if row.get("ready"):
        return text(row.get("auth_kind")) or "ready"
    missing = row.get("missing") or []
    return "needs " + ", ".join(text(item) for item in missing)


@resolver("client", "client_id", "oauth_client_id")
def clients(ui: Ui, path: tuple[str, ...], state: LeafState) -> list[Named]:
    del path
    params = {}
    provider = state.get("provider_id")
    if provider:
        params["provider_id"] = provider
    rows = fetch(ui, "/api/oauth-clients", **params)
    return [
        Named(
            text(row.get("id")),
            text(row.get("label")) or text(row.get("id")),
            f"{text(row.get('provider_id'))}  {text(row.get('project_id'))}",
        )
        for row in rows
    ]
