from __future__ import annotations

import sys

from downcroc.cli.client import api, get
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.runtime.paths import Paths


class AddressBook:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths
        self._map: dict[str, str] = {}
        self._warned = False

    def refresh(self) -> None:
        found: dict[str, str] = {}
        try:
            with api(self._paths, timeout=2) as client:
                for params in ({}, {"archived": "true"}):
                    for row in get(client, "/api/accounts", **params):
                        found[str(row["id"])] = str(row["address"])
        except CliError:
            if not self._warned:
                print(
                    "warning: account addresses unavailable, showing ids",
                    file=sys.stderr,
                )
                self._warned = True
            return
        self._map = found

    def filter(self, wanted: str | None) -> str | None:
        if not wanted:
            return None
        folded = wanted.casefold()
        for account_id, address in self._map.items():
            if address.casefold() == folded:
                return account_id
        return wanted

    def apply(self, entry: dict, *, json_mode: bool) -> dict:
        if not self._map:
            return entry
        if json_mode:
            account = entry.get("account") or entry.get("account_id")
            if account in self._map:
                entry = {**entry, "account_address": self._map[account]}
            return entry
        result = dict(entry)
        for key in ("account", "account_id"):
            value = result.get(key)
            if value in self._map:
                result[key] = self._map[value]
        scope = result.get("scope")
        if scope in self._map:
            result["scope"] = self._map[scope]
        accounts = result.get("accounts")
        if isinstance(accounts, list):
            result["accounts"] = [self._map.get(item, item) for item in accounts]
        return result


def load_book() -> AddressBook:
    paths, _, _ = load()
    book = AddressBook(paths)
    book.refresh()
    return book
