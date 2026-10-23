from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.errors import BatchInvalid


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    field: str
    key: str | None = None
    row: int | None = None

    def as_detail(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }
        if self.key is not None:
            detail["key"] = self.key
        if self.row is not None:
            detail["row"] = self.row
        return detail


class Issues:
    def __init__(self) -> None:
        self._items: list[Issue] = []

    def add(
        self,
        code: str,
        message: str,
        field: str,
        *,
        key: str | None = None,
        row: int | None = None,
    ) -> None:
        self._items.append(
            Issue(code=code, message=message, field=field, key=key, row=row)
        )

    def extend(self, items: list[Issue]) -> None:
        self._items.extend(items)

    @property
    def items(self) -> list[Issue]:
        return list(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def raise_if_any(self) -> None:
        if not self._items:
            return
        first = self._items[0]
        raise BatchInvalid(
            f"{len(self._items)} problem(s) in the source, first: {first.message}",
            details=[item.as_detail() for item in self._items],
        )
