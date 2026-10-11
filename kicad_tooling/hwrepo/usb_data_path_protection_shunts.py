"""Exact source checks for project-mapped multi-pin USB protection shunts."""

from __future__ import annotations

from .models import NetlistContract
from .usb_data_path_component_checks import check_usb_component_pin_map
from .usb_data_path_models import UsbDataInterfaceRequirement
from .usb_data_path_types import UsbDataPathMismatch


def protection_shunt_mismatches(
    interface: UsbDataInterfaceRequirement,
    observed: NetlistContract,
) -> tuple[UsbDataPathMismatch, ...]:
    """Return one exact-map fault for each miswired mapped protection component."""
    mismatches: list[UsbDataPathMismatch] = []
    for requirement in interface.protection_shunts:
        check = check_usb_component_pin_map(requirement, observed)
        issues = (*check.component_issues, *(message for _pin, message in check.pin_issues))
        if not issues:
            continue
        assignments = tuple(
            sorted(
                (
                    f"{item.pin}={item.net}"
                    if item.disposition == "net"
                    else f"{item.pin}=<unconnected>"
                    for item in requirement.pins
                ),
                key=lambda item: (item.casefold(), item),
            )
        )
        mismatches.append(
            UsbDataPathMismatch(
                interface_id=interface.id,
                basis=interface.basis,
                line="protection_shunt",
                connector_reference=interface.connector_reference,
                connector_symbol=interface.expected_connector_symbol,
                connector_footprint=interface.expected_connector_footprint,
                connector_pin=", ".join(
                    item.pin for item in requirement.data_pins if item.line == "D+"
                ),
                connector_net=interface.positive.connector_net,
                phy_reference=interface.phy_reference,
                phy_symbol=interface.expected_phy_symbol,
                phy_footprint=interface.expected_phy_footprint,
                phy_pin=", ".join(item.pin for item in requirement.data_pins if item.line == "D-"),
                phy_net=interface.negative.connector_net,
                expected_topology=f"mapped protection shunt {requirement.reference}",
                series_resistor_reference=None,
                series_resistor_symbol=None,
                series_resistor_footprint=None,
                series_resistance_range_ohms=None,
                issues=tuple(issues),
                protection_shunt_reference=requirement.reference,
                protection_shunt_identity=(
                    f"{requirement.expected_symbol}; {requirement.expected_footprint}"
                ),
                protection_shunt_pin_assignments=assignments,
            )
        )
    return tuple(mismatches)
