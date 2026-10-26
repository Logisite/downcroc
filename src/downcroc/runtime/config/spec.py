from __future__ import annotations

from copy import deepcopy
from typing import Any

from downcroc.runtime.config.schema import Settings

RANGE_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
)
ITEM_KEYS = ("minimum", "maximum", "minLength", "maxLength")


def _type_of(schema: dict[str, Any]) -> str:
    kind = schema.get("type")
    if isinstance(kind, str):
        return kind
    for option in schema.get("anyOf", []):
        option_type = option.get("type")
        if isinstance(option_type, str) and option_type != "null":
            return option_type
    values = schema.get("enum")
    if values:
        return type(values[0]).__name__
    return "unknown"


def _range_of(schema: dict[str, Any]) -> dict[str, Any] | None:
    found = {key: schema[key] for key in RANGE_KEYS if key in schema}
    items = schema.get("items", {})
    for key in ITEM_KEYS:
        if key in items:
            found[f"item_{key}"] = items[key]
    return found or None


def _defaults() -> dict[str, Any]:
    return Settings().model_dump(mode="json")


def describe() -> list[dict[str, Any]]:
    schema = Settings.model_json_schema()
    definitions = schema.get("$defs", {})
    defaults = _defaults()
    fields: list[dict[str, Any]] = []
    for section, section_schema in schema.get("properties", {}).items():
        ref = section_schema.get("$ref")
        if not ref:
            continue
        model = definitions.get(ref.rsplit("/", 1)[-1], {})
        for name, field_schema in model.get("properties", {}).items():
            fields.append(
                {
                    "path": f"{section}.{name}",
                    "section": section,
                    "name": name,
                    "type": _type_of(field_schema),
                    "default": defaults.get(section, {}).get(name),
                    "range": _range_of(field_schema),
                    "values": field_schema.get("enum"),
                    "description": field_schema.get("description", ""),
                    "restart_required": bool(
                        field_schema.get("restart_required", False)
                    ),
                }
            )
    return fields


def flatten(document: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in document.items():
        if isinstance(value, dict):
            for nested, nested_value in flatten(value).items():
                flat[f"{key}.{nested}"] = nested_value
        else:
            flat[key] = value
    return flat


def changed_paths(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    before = flatten(old)
    after = flatten(new)
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in patch.items():
        current = result.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            result[key] = merge(current, value)
        else:
            result[key] = deepcopy(value)
    return result
