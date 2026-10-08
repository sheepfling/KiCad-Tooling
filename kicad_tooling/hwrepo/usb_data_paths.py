"""Source-bound checks for project-authored USB connector-to-PHY path maps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar

from .bus_heuristics import direct_resistors, usb_data_function_identity
from .models import (
    ComponentContract,
    NetlistContract,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)
from .reference_bonds import reference_bond_issues
from .usb_peer_reference_review import usb_endpoint_reference_pins

_Value = TypeVar("_Value")


@dataclass(frozen=True)
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


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _pin_nets(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            net
            for net, pins in observed.nets.items()
            if any(candidate.casefold() == pin.casefold() for candidate in pins)
        )
    )


def _endpoint_data_pins(
    observed: NetlistContract,
    reference: str,
    line: str,
    data_port_group: str | None,
) -> tuple[str, ...]:
    side = "positive" if line == "D+" else "negative"
    return tuple(
        sorted(
            (
                pin
                for pin, function in observed.pin_functions.items()
                if pin.rpartition(".")[0].casefold() == reference.casefold()
                and (identity := usb_data_function_identity(function)) is not None
                and identity[1] == side
                and (
                    data_port_group is None or identity[0] is None or identity[0] == data_port_group
                )
            ),
            key=lambda item: (item.casefold(), item),
        )
    )


def _component_issues(
    observed: NetlistContract,
    reference: str,
    expected_symbol: str,
    expected_footprint: str,
    expected_pins: tuple[str, ...],
) -> list[str]:
    issues: list[str] = []
    component = _lookup(observed.components, reference)
    if not isinstance(component, ComponentContract):
        return [f"{reference} is absent or ambiguous in the native netlist"]
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )
    symbol = _lookup(observed.component_symbols, reference)
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{reference} is marked DNP")
    pin_numbers = _lookup(observed.component_pin_numbers, reference)
    if pin_numbers is None:
        issues.append(f"{reference} native pin inventory is unavailable")
    else:
        actual_numbers = {str(number).casefold() for number in pin_numbers}
        for expected_pin in expected_pins:
            expected_number = expected_pin.rsplit(".", 1)[1].casefold()
            if expected_number not in actual_numbers:
                issues.append(f"{expected_pin} is absent from the native pin inventory")
    return issues


def _identity_issues(
    observed: NetlistContract,
    requirement: UsbDataInterfaceRequirement,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
) -> list[str]:
    return [
        *_component_issues(
            observed,
            requirement.connector_reference,
            requirement.expected_connector_symbol,
            requirement.expected_connector_footprint,
            connector_pins,
        ),
        *_component_issues(
            observed,
            requirement.phy_reference,
            requirement.expected_phy_symbol,
            requirement.expected_phy_footprint,
            phy_pins,
        ),
    ]


def _resistor_issues(
    observed: NetlistContract,
    requirement: UsbDataPathLineRequirement,
    connector_net: str,
    phy_net: str,
) -> list[str]:
    resistor = requirement.series_resistor
    if resistor is None:
        return []
    issues: list[str] = []
    component = _lookup(observed.components, resistor.reference)
    if not isinstance(component, ComponentContract):
        return [f"{resistor.reference} is absent or ambiguous in the native netlist"]
    if component.footprint != resistor.expected_footprint:
        issues.append(
            f"{resistor.reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {resistor.expected_footprint}"
        )
    symbol = _lookup(observed.component_symbols, resistor.reference)
    if symbol != resistor.expected_symbol:
        issues.append(
            f"{resistor.reference} symbol is {symbol or '<unknown>'}; "
            f"expected {resistor.expected_symbol}"
        )
    if resistor.reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{resistor.reference} is marked DNP but the mapped path requires it fitted")

    pin_numbers = _lookup(observed.component_pin_numbers, resistor.reference)
    if pin_numbers is None:
        issues.append(f"{resistor.reference} native pin inventory is unavailable")
    elif len(pin_numbers) != 2:
        issues.append(f"{resistor.reference} has {len(pin_numbers)} native pins; expected two")

    actual = next(
        (
            item
            for item in direct_resistors(observed)
            if item.reference.casefold() == resistor.reference.casefold()
        ),
        None,
    )
    if actual is None:
        issues.append(
            f"{resistor.reference} is not a fitted, conventional two-terminal resistor "
            "with two unique net assignments"
        )
    else:
        expected_nets = {connector_net.casefold(), phy_net.casefold()}
        actual_nets = {actual.first_net.casefold(), actual.second_net.casefold()}
        if actual_nets != expected_nets:
            issues.append(
                f"{resistor.reference} spans {actual.first_net}/{actual.second_net}; "
                f"expected {connector_net}/{phy_net}"
            )
        if not resistor.minimum_ohms <= actual.resistance_ohms <= resistor.maximum_ohms:
            issues.append(
                f"{resistor.reference} is {actual.resistance_ohms:g} Ω; expected "
                f"{resistor.minimum_ohms:g}–{resistor.maximum_ohms:g} Ω"
            )
    return issues


def _reference_issues(
    observed: NetlistContract, interface: UsbDataInterfaceRequirement
) -> tuple[str, ...]:
    if interface.reference_policy is None:
        return ()
    connector_first_pin = interface.connector_reference_pins[0].pin
    phy_first_pin = interface.phy_reference_pins[0].pin
    issues = [
        *_component_issues(
            observed,
            interface.connector_reference,
            interface.expected_connector_symbol,
            interface.expected_connector_footprint,
            (connector_first_pin,),
        ),
        *_component_issues(
            observed,
            interface.phy_reference,
            interface.expected_phy_symbol,
            interface.expected_phy_footprint,
            (phy_first_pin,),
        ),
    ]
    connector_observed = usb_endpoint_reference_pins(observed, interface.connector_reference)
    phy_observed = usb_endpoint_reference_pins(observed, interface.phy_reference)
    if connector_observed is None:
        issues.append(
            f"{interface.connector_reference} has incomplete, ambiguous, or unsupported reference-pin evidence"
        )
    if phy_observed is None:
        issues.append(
            f"{interface.phy_reference} has incomplete, ambiguous, or unsupported reference-pin evidence"
        )
    if connector_observed is None or phy_observed is None:
        return tuple(issues)

    connector_expected = {
        (item.pin.casefold(), item.net.casefold()) for item in interface.connector_reference_pins
    }
    phy_expected = {
        (item.pin.casefold(), item.net.casefold()) for item in interface.phy_reference_pins
    }
    connector_actual = {(item.pin.casefold(), item.net.casefold()) for item in connector_observed}
    phy_actual = {(item.pin.casefold(), item.net.casefold()) for item in phy_observed}
    if {pin for pin, _ in connector_expected} != {pin for pin, _ in connector_actual}:
        issues.append(
            f"{interface.connector_reference} mapped reference-pin inventory does not match the native return pins"
        )
    elif connector_expected != connector_actual:
        issues.append(
            f"{interface.connector_reference} reference assignments differ from the mapped nets"
        )
    if {pin for pin, _ in phy_expected} != {pin for pin, _ in phy_actual}:
        issues.append(
            f"{interface.phy_reference} mapped reference-pin inventory does not match the native return pins"
        )
    elif phy_expected != phy_actual:
        issues.append(
            f"{interface.phy_reference} reference assignments differ from the mapped nets"
        )
    if interface.reference_policy == "bonded" and interface.reference_bond is not None:
        issues.extend(reference_bond_issues(observed, interface.reference_bond))
    return tuple(issues)


def usb_data_path_mismatches(
    path_map: UsbDataPathMap, observed: NetlistContract
) -> tuple[UsbDataPathMismatch, ...]:
    """Compare exact project-selected direct or resistor paths with native pin/net evidence."""
    mismatches: list[UsbDataPathMismatch] = []
    for interface in path_map.interfaces:
        reference_issues = _reference_issues(observed, interface)
        for line in (interface.positive, interface.negative):
            connector_data_pins = _endpoint_data_pins(
                observed,
                interface.connector_reference,
                line.line,
                interface.data_port_group,
            )
            phy_data_pins = _endpoint_data_pins(
                observed,
                interface.phy_reference,
                line.line,
                interface.data_port_group,
            )
            issues = _identity_issues(
                observed,
                interface,
                line.connector_pins,
                line.phy_pins,
            )
            if connector_data_pins and {pin.casefold() for pin in connector_data_pins} != {
                pin.casefold() for pin in line.connector_pins
            }:
                issues.append(
                    f"{interface.connector_reference} mapped {line.line} pin inventory "
                    "does not match native USB data pin functions"
                )
            if phy_data_pins and {pin.casefold() for pin in phy_data_pins} != {
                pin.casefold() for pin in line.phy_pins
            }:
                issues.append(
                    f"{interface.phy_reference} mapped {line.line} pin inventory "
                    "does not match native USB data pin functions"
                )
            for pin in line.connector_pins:
                connector_nets = _pin_nets(observed, pin)
                if connector_nets != (line.connector_net,):
                    issues.append(
                        f"{pin} is on {', '.join(connector_nets) or 'unconnected'}; "
                        f"expected {line.connector_net}"
                    )
            for pin in line.phy_pins:
                phy_nets = _pin_nets(observed, pin)
                if phy_nets != (line.phy_net,):
                    issues.append(
                        f"{pin} is on {', '.join(phy_nets) or 'unconnected'}; "
                        f"expected {line.phy_net}"
                    )
            if line.topology == "series_resistor":
                issues.extend(_resistor_issues(observed, line, line.connector_net, line.phy_net))
            if issues:
                mismatches.append(
                    UsbDataPathMismatch(
                        interface_id=interface.id,
                        basis=interface.basis,
                        line=line.line,
                        connector_reference=interface.connector_reference,
                        connector_symbol=interface.expected_connector_symbol,
                        connector_footprint=interface.expected_connector_footprint,
                        connector_pin=", ".join(line.connector_pins),
                        connector_net=line.connector_net,
                        phy_reference=interface.phy_reference,
                        phy_symbol=interface.expected_phy_symbol,
                        phy_footprint=interface.expected_phy_footprint,
                        phy_pin=", ".join(line.phy_pins),
                        phy_net=line.phy_net,
                        expected_topology=line.topology,
                        series_resistor_reference=(
                            None if line.series_resistor is None else line.series_resistor.reference
                        ),
                        series_resistor_symbol=(
                            None
                            if line.series_resistor is None
                            else line.series_resistor.expected_symbol
                        ),
                        series_resistor_footprint=(
                            None
                            if line.series_resistor is None
                            else line.series_resistor.expected_footprint
                        ),
                        series_resistance_range_ohms=(
                            None
                            if line.series_resistor is None
                            else (
                                line.series_resistor.minimum_ohms,
                                line.series_resistor.maximum_ohms,
                            )
                        ),
                        issues=tuple(issues),
                    )
                )
        if reference_issues:
            mismatches.append(
                UsbDataPathMismatch(
                    interface_id=interface.id,
                    basis=interface.basis,
                    line="reference",
                    connector_reference=interface.connector_reference,
                    connector_symbol=interface.expected_connector_symbol,
                    connector_footprint=interface.expected_connector_footprint,
                    connector_pin=", ".join(
                        item.pin for item in interface.connector_reference_pins
                    ),
                    connector_net=", ".join(
                        item.net for item in interface.connector_reference_pins
                    ),
                    phy_reference=interface.phy_reference,
                    phy_symbol=interface.expected_phy_symbol,
                    phy_footprint=interface.expected_phy_footprint,
                    phy_pin=", ".join(item.pin for item in interface.phy_reference_pins),
                    phy_net=", ".join(item.net for item in interface.phy_reference_pins),
                    expected_topology=f"reference_policy={interface.reference_policy}",
                    series_resistor_reference=None,
                    series_resistor_symbol=None,
                    series_resistor_footprint=None,
                    series_resistance_range_ohms=None,
                    issues=reference_issues,
                    reference_policy=interface.reference_policy,
                    reference_bond_reference=(
                        None
                        if interface.reference_bond is None
                        else interface.reference_bond.reference
                    ),
                    reference_bond_identity=(
                        None
                        if interface.reference_bond is None
                        else (
                            f"{interface.reference_bond.expected_symbol}; "
                            f"{interface.reference_bond.expected_footprint}; "
                            f"{interface.reference_bond.expected_value}"
                        )
                    ),
                    reference_bond_side_a=(
                        None
                        if interface.reference_bond is None
                        else f"{interface.reference_bond.side_a_pin} on "
                        f"{interface.reference_bond.side_a_net}"
                    ),
                    reference_bond_side_b=(
                        None
                        if interface.reference_bond is None
                        else f"{interface.reference_bond.side_b_pin} on "
                        f"{interface.reference_bond.side_b_net}"
                    ),
                )
            )
    return tuple(mismatches)
