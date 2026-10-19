"""Exact case-insensitive lookup for native and project-owned mapping keys."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

_Value = TypeVar("_Value")


def lookup_unique_casefold(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    """Return a value only when exactly one key matches without case sensitivity."""
    match: _Value | None = None
    found = False
    folded_key = key.casefold()
    for candidate, value in mapping.items():
        if candidate.casefold() != folded_key:
            continue
        if found:
            return None
        match = value
        found = True
    return match if found else None
