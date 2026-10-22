from __future__ import annotations

from typing import Protocol


class SecretLike(Protocol):
    value: str
    expires_at: str | None
    scopes: tuple[str, ...]


class SecretStore(Protocol):
    def get_secret(self, key: str) -> SecretLike: ...

    def set_secrets(
        self,
        records: dict[str, tuple[str, str | None, tuple[str, ...]]],
    ) -> None: ...

    def delete_secret(self, key: str) -> bool: ...

    def keys(self) -> list[str]: ...
