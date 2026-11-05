"""Exact case-insensitive lookup for native and project-owned mapping keys."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeAlias, TypeVar

_Value = TypeVar("_Value")
CasefoldedUniqueIndex: TypeAlias = Mapping[str, _Value]


def casefolded_unique_index(
    mapping: Mapping[str, _Value],
) -> CasefoldedUniqueIndex[_Value]:
    """Return an immutable case-fold index, omitting ambiguous source keys.

    Source mappings may contain distinct spellings such as ``U1`` and ``u1``.
    They are both omitted from the index instead of selecting whichever value
    happened to be inserted last.
    """
    unique: dict[str, _Value] = {}
    ambiguous: set[str] = set()
    for key, value in mapping.items():
        folded = key.casefold()
        if folded in ambiguous:
            continue
        if folded in unique:
            del unique[folded]
            ambiguous.add(folded)
            continue
        unique[folded] = value
    return MappingProxyType(unique)


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
