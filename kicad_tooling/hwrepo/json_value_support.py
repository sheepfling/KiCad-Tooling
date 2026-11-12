"""Canonical JSON value representation shared by source-bound lint checks."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import JsonValue

JsonValueTypeName = Literal["null", "boolean", "number", "string", "array", "object"]


def canonical_json_value(value: JsonValue) -> str:
    """Serialize a JSON value with stable key order and no non-finite numbers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_value_type_name(value: JsonValue) -> JsonValueTypeName:
    """Return a JSON type name without treating booleans as numbers."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"
