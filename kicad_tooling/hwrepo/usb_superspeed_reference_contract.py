"""Compare authored USB SuperSpeed reference maps with source-bound peer paths."""

from __future__ import annotations

from .models import NetlistContract
from .reference_bonds import reference_bond_issues
from .usb_data_path_models import UsbDataPathMap
from .usb_data_path_types import UsbDataPathMismatch
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews
from .usb_peer_reference_types import UsbPeerReferencePathCoverage
from .usb_superspeed_reference_models import UsbSuperspeedReferencePathRequirement


def _interface_paths(
    requirement: UsbSuperspeedReferencePathRequirement,
    entries: tuple[UsbPeerReferencePathCoverage, ...],
) -> tuple[UsbPeerReferencePathCoverage, ...]:
    return tuple(
        item
        for item in entries
        if item.connector_reference.casefold() == requirement.connector_reference.casefold()
        and item.phy_reference.casefold() == requirement.phy_reference.casefold()
        and item.data_link.connector_signal_family == requirement.connector_signal_family
        and item.data_link.phy_signal_family == requirement.phy_signal_family
    )


def _path_issues(
    requirement: UsbSuperspeedReferencePathRequirement,
    observed: NetlistContract,
    path: UsbPeerReferencePathCoverage,
) -> tuple[str, ...]:
    issues: list[str] = []
    if (
        path.connector_symbol != requirement.expected_connector_symbol
        or path.connector_footprint != requirement.expected_connector_footprint
    ):
        issues.append(
            f"{requirement.connector_reference} identity differs from the mapped connector"
        )
    if path.phy_symbol != requirement.expected_phy_symbol or path.phy_footprint != (
        requirement.expected_phy_footprint
    ):
        issues.append(f"{requirement.phy_reference} identity differs from the mapped PHY")

    data = path.data_link
    expected_data = (
        (requirement.connector_positive_pin.casefold(),),
        (requirement.phy_positive_pin.casefold(),),
        requirement.positive_net.casefold(),
        requirement.positive_net.casefold(),
        (requirement.connector_negative_pin.casefold(),),
        (requirement.phy_negative_pin.casefold(),),
        requirement.negative_net.casefold(),
        requirement.negative_net.casefold(),
    )
    actual_data = (
        tuple(pin.casefold() for pin in data.connector_positive_pins),
        tuple(pin.casefold() for pin in data.phy_positive_pins),
        data.connector_positive_net.casefold(),
        data.phy_positive_net.casefold(),
        tuple(pin.casefold() for pin in data.connector_negative_pins),
        tuple(pin.casefold() for pin in data.phy_negative_pins),
        data.connector_negative_net.casefold(),
        data.phy_negative_net.casefold(),
    )
    if actual_data != expected_data:
        issues.append("USB SuperSpeed positive or negative pin/net assignments differ from the map")

    expected_connector_references = {
        (item.pin.casefold(), item.net.casefold()) for item in requirement.connector_reference_pins
    }
    expected_phy_references = {
        (item.pin.casefold(), item.net.casefold()) for item in requirement.phy_reference_pins
    }
    actual_connector_references = {
        (item.pin.casefold(), item.net.casefold()) for item in path.connector_reference_pins
    }
    actual_phy_references = {
        (item.pin.casefold(), item.net.casefold()) for item in path.phy_reference_pins
    }
    if expected_connector_references != actual_connector_references:
        issues.append(
            f"{requirement.connector_reference} reference pins or nets differ from the map"
        )
    if expected_phy_references != actual_phy_references:
        issues.append(f"{requirement.phy_reference} reference pins or nets differ from the map")

    common = path.connector_reference_net.casefold() == path.phy_reference_net.casefold()
    if (requirement.reference_policy == "common_net") != common:
        issues.append(
            f"observed endpoint reference relationship differs from {requirement.reference_policy}"
        )
    if requirement.reference_policy == "bonded" and requirement.reference_bond is not None:
        issues.extend(reference_bond_issues(observed, requirement.reference_bond))
    return tuple(sorted(set(issues)))


def _mismatch(
    requirement: UsbSuperspeedReferencePathRequirement,
    issues: tuple[str, ...],
) -> UsbDataPathMismatch:
    connector_nets = tuple(sorted({item.net for item in requirement.connector_reference_pins}))
    phy_nets = tuple(sorted({item.net for item in requirement.phy_reference_pins}))
    bond = requirement.reference_bond
    return UsbDataPathMismatch(
        interface_id=requirement.id,
        basis=requirement.basis,
        line="reference",
        connector_reference=requirement.connector_reference,
        connector_symbol=requirement.expected_connector_symbol,
        connector_footprint=requirement.expected_connector_footprint,
        connector_pin=", ".join(sorted(item.pin for item in requirement.connector_reference_pins)),
        connector_net=", ".join(connector_nets),
        phy_reference=requirement.phy_reference,
        phy_symbol=requirement.expected_phy_symbol,
        phy_footprint=requirement.expected_phy_footprint,
        phy_pin=", ".join(sorted(item.pin for item in requirement.phy_reference_pins)),
        phy_net=", ".join(phy_nets),
        expected_topology="direct USB SuperSpeed P/N pair",
        series_resistor_reference=None,
        series_resistor_symbol=None,
        series_resistor_footprint=None,
        series_resistance_range_ohms=None,
        issues=issues,
        reference_policy=requirement.reference_policy,
        reference_bond_reference=None if bond is None else bond.reference,
        reference_bond_identity=(
            None
            if bond is None
            else f"{bond.expected_symbol}; {bond.expected_footprint}; {bond.expected_value}"
        ),
        reference_bond_side_a=None if bond is None else f"{bond.side_a_pin}={bond.side_a_net}",
        reference_bond_side_b=None if bond is None else f"{bond.side_b_pin}={bond.side_b_net}",
    )


def usb_superspeed_reference_mismatches(
    path_map: UsbDataPathMap,
    observed: NetlistContract,
) -> tuple[UsbDataPathMismatch, ...]:
    """Report stale exact SuperSpeed reference maps without hiding peer prompts."""
    if not path_map.superspeed_interfaces:
        return ()
    scan = scan_usb_peer_reference_reviews(observed, path_map)
    mismatches: list[UsbDataPathMismatch] = []
    for requirement in path_map.superspeed_interfaces:
        paths = _interface_paths(requirement, scan.coverage.path_entries)
        if not paths:
            issues = (
                "No supported direct USB SuperSpeed path matches the mapped connector/PHY pair",
            )
        else:
            issues = tuple(
                sorted(
                    {issue for path in paths for issue in _path_issues(requirement, observed, path)}
                )
            )
        if issues:
            mismatches.append(_mismatch(requirement, issues))
    return tuple(mismatches)
