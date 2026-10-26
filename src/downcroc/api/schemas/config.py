from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigFieldOut(BaseModel):
    path: str
    section: str
    name: str
    type: str
    default: Any
    range: dict[str, Any] | None = None
    values: list[Any] | None = None
    description: str
    restart_required: bool = False


class ConfigSchemaOut(BaseModel):
    version: int = 1
    fields: list[ConfigFieldOut]


class ConfigOut(BaseModel):
    config: dict[str, Any]
    document: dict[str, Any] | None
    path: str
    error: str | None = None


class ConfigPatchOut(BaseModel):
    changed: list[str]
    config: dict[str, Any]
