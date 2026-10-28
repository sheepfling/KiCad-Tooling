"""Typed findings emitted by USB path map comparison services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UsbDataPathMismatch:
    interface_id: str
    basis: str
    line: str
    connector_reference: str
    connector_symbol: str
    connector_footprint: str
    connector_pin: str
    connector_net: str
    phy_reference: str
    phy_symbol: str
    phy_footprint: str
    phy_pin: str
    phy_net: str
    expected_topology: str
    series_resistor_reference: str | None
    series_resistor_symbol: str | None
    series_resistor_footprint: str | None
    series_resistance_range_ohms: tuple[float, float] | None
    issues: tuple[str, ...]
    reference_policy: str | None = None
    reference_bond_reference: str | None = None
    reference_bond_identity: str | None = None
    reference_bond_side_a: str | None = None
    reference_bond_side_b: str | None = None
    inline_component_reference: str | None = None
    inline_component_identity: str | None = None
    inline_component_pin_assignments: tuple[str, ...] = ()
    protection_shunt_reference: str | None = None
    protection_shunt_identity: str | None = None
    protection_shunt_pin_assignments: tuple[str, ...] = ()
