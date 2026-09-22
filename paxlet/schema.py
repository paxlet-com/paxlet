from __future__ import annotations

from typing import Any

from .errors import RuntimeError


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_value(value: Any, schema: dict[str, Any] | None, label: str = "value") -> None:
    """Validate the intentionally small JSON-Schema subset in Core 0.1."""
    if not schema:
        return
    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        raise RuntimeError(f"{label} must be {expected}")
    if expected == "object" and isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise RuntimeError(f"{label}.{key} is required")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value and isinstance(child_schema, dict):
                validate_value(value[key], child_schema, f"{label}.{key}")
    if expected == "array" and isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            validate_value(item, schema["items"], f"{label}[{index}]")
