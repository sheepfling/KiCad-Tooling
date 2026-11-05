"""Exact component identity comparisons against a native schematic netlist."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract


def component_identity_issues(
    observed: NetlistContract,
    reference: str,
    expected_value: str | None,
    expected_symbol: str,
    expected_footprint: str,
) -> tuple[str, ...]:
    """Describe identity differences without resolving ambiguous source keys."""
    component = lookup_unique_casefold(observed.components, reference)
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    if component is None:
        return (f"Mapped component {reference} is missing or ambiguous in the native netlist",)
    issues: list[str] = []
    if expected_value is not None and component.value != expected_value:
        issues.append(f"{reference} value is {component.value}; expected {expected_value}")
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )
    return tuple(issues)
