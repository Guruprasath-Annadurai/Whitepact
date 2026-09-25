# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validate MCP tool arguments at the dispatch boundary.

Malformed types (e.g. passing a string where an object is required) must not
reach handler code and surface as AttributeError / tool_execution_failed.
"""

from __future__ import annotations

from typing import Any


def _invalid(field: str, message: str) -> dict[str, Any]:
    return {
        "error": "invalid_argument",
        "field": field,
        "message": message,
    }


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _check_type(field: str, value: Any, schema_type: str | list[str]) -> dict[str, Any] | None:
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    actual = _type_name(value)
    allowed = set(types)
    # JSON Schema integer is also a number
    if "number" in allowed and actual == "integer":
        return None
    if actual in allowed:
        return None
    return _invalid(field, f"Expected type {', '.join(types)}; received {actual}.")


def _validate_value(field: str, value: Any, schema: dict[str, Any]) -> dict[str, Any] | None:
    if value is None:
        if schema.get("type") == "null" or "null" in schema.get("type", []):
            return None
        if schema.get("type") is not None:
            return _invalid(field, "Value must not be null.")
        return None

    schema_type = schema.get("type")
    if schema_type is not None:
        err = _check_type(field, value, schema_type)
        if err:
            return err

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            return _invalid(field, f"Value must be >= {minimum}.")
        if maximum is not None and value > maximum:
            return _invalid(field, f"Value must be <= {maximum}.")

    if isinstance(value, str) and "enum" in schema:
        enum_vals = schema["enum"]
        if value not in enum_vals:
            return _invalid(
                field,
                f"Value must be one of: {', '.join(str(v) for v in enum_vals)}.",
            )

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                err = _validate_value(f"{field}[{index}]", item, item_schema)
                if err:
                    return err

    if isinstance(value, dict):
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_field = f"{field}.{key}" if field else key
            if key in props:
                err = _validate_value(child_field, item, props[key])
                if err:
                    return err
            elif additional is False:
                return _invalid(field, f"Unknown field '{key}' is not allowed.")
            elif isinstance(additional, dict):
                err = _validate_value(child_field, item, additional)
                if err:
                    return err
        if additional is False and props:
            unknown = set(value) - set(props)
            if unknown:
                return _invalid(
                    field,
                    f"Unknown field(s): {', '.join(sorted(unknown))}.",
                )
    return None


def validate_tool_arguments(
    tool_name: str,
    raw_args: Any,
    schema: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (normalized_args, error_dict)."""
    if not isinstance(raw_args, dict):
        return None, _invalid("arguments", "Tool arguments must be a JSON object.")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in raw_args:
            return None, _invalid(key, "Required field is missing.")

    additional = schema.get("additionalProperties", True)
    if additional is False and properties:
        unknown = set(raw_args) - set(properties)
        if unknown:
            return None, _invalid("arguments", f"Unknown field(s): {', '.join(sorted(unknown))}.")

    for key, value in raw_args.items():
        prop_schema = properties.get(key)
        if prop_schema is None:
            if additional is False:
                return None, _invalid(key, "Unknown field is not allowed.")
            continue
        err = _validate_value(key, value, prop_schema)
        if err:
            err["tool"] = tool_name
            return None, err

    return raw_args, None
