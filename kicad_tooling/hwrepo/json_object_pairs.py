"""Lossless JSON object-member handling for narrowly scoped duplicate-key reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class JsonObjectPairs:
    """Decoded JSON object members in their original order, including duplicates."""

    pairs: tuple[tuple[str, object], ...]


def retain_json_object_pairs(pairs: list[tuple[str, Any]]) -> JsonObjectPairs:
    """Use as ``json.loads(object_pairs_hook=...)`` to retain object members."""
    return JsonObjectPairs(tuple(pairs))


def json_object_member(value: object, key: str) -> object | None:
    """Return the last saved value for a key in a retained JSON object."""
    if not isinstance(value, JsonObjectPairs):
        return None
    return next((item for name, item in reversed(value.pairs) if name == key), None)


def json_value_from_object_pairs(
    value: object,
    *,
    allowed_duplicate_object_paths: frozenset[tuple[str, ...]] = frozenset(),
    allowed_duplicate_object_members: frozenset[tuple[tuple[str, ...], str]] = frozenset(),
    current_path: tuple[str, ...] = (),
) -> JsonValue:
    """Convert retained pairs to JSON values, rejecting unapproved duplicates."""
    if isinstance(value, JsonObjectPairs):
        result: dict[str, JsonValue] = {}
        for key, item in value.pairs:
            if (
                key in result
                and current_path not in allowed_duplicate_object_paths
                and (
                    current_path,
                    key,
                )
                not in allowed_duplicate_object_members
            ):
                path = ".".join(current_path) or "<root>"
                raise ValueError(f"Duplicate JSON key at {path}: {key}")
            result[key] = json_value_from_object_pairs(
                item,
                allowed_duplicate_object_paths=allowed_duplicate_object_paths,
                allowed_duplicate_object_members=allowed_duplicate_object_members,
                current_path=(*current_path, key),
            )
        return result
    if isinstance(value, list):
        items = cast(list[object], value)
        return [
            json_value_from_object_pairs(
                item,
                allowed_duplicate_object_paths=allowed_duplicate_object_paths,
                allowed_duplicate_object_members=allowed_duplicate_object_members,
                current_path=current_path,
            )
            for item in items
        ]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported decoded JSON value: {type(value).__name__}")


def json_object_pairs_source_order_value(value: object) -> JsonValue:
    """Represent every object as ordered key/value pairs without collapsing duplicates."""
    if isinstance(value, JsonObjectPairs):
        return [[key, json_object_pairs_source_order_value(item)] for key, item in value.pairs]
    if isinstance(value, list):
        items = cast(list[object], value)
        return [json_object_pairs_source_order_value(item) for item in items]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported decoded JSON value: {type(value).__name__}")
