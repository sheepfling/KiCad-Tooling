"""Typed records for reviewed connector comparison scopes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ConnectorComparisonScope:
    """Reviewed comparison group and its source-authored basis for one connector."""

    group: str
    basis: str


ConnectorComparisonScopes = Mapping[str, ConnectorComparisonScope]


def connector_comparison_scopes_by_reference(
    scopes: ConnectorComparisonScopes | None,
) -> ConnectorComparisonScopes:
    """Freeze a scope index with case-insensitive, unique connector references."""
    normalized: dict[str, ConnectorComparisonScope] = {}
    for reference, scope in (scopes or {}).items():
        key = reference.casefold()
        if key in normalized:
            raise ValueError("Reviewed connector references must be unique")
        normalized[key] = scope
    return MappingProxyType(normalized)
