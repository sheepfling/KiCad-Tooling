"""Usb c vbus for deterministic KiCad bus analysis."""

from __future__ import annotations

from decimal import Decimal

from .crystal_networks import parse_capacitance_pf
from .models import (
    ComponentContract,
    ElectricalCheck,
    NetlistContract,
    UsbCVbusCapacitanceRequirement,
    UsbCVbusPathRequirement,
)


def usb_c_vbus_path_check(
    requirement: UsbCVbusPathRequirement,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Compare one authored component and net chain with the native pin inventory."""
    issues: list[str] = []
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    for pin, expected_net in (
        (requirement.connector_pin, requirement.connector_net),
        (requirement.board_pin, requirement.board_net),
    ):
        assigned = pin_nets.get(pin.casefold(), set())
        if assigned != {expected_net}:
            actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
            issues.append(f"{pin} is assigned to {actual}; expected only {expected_net}")

    for element in requirement.elements:
        key = element.reference.casefold()
        component_matches = [
            (reference, component)
            for reference, component in observed.components.items()
            if reference.casefold() == key
        ]
        if len(component_matches) != 1:
            issues.append(
                f"{element.reference} is "
                + ("absent" if not component_matches else "ambiguous")
                + " in the native netlist"
            )
            continue

        reference, component = component_matches[0]
        if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
            issues.append(f"{reference} is DNP but the VBUS path requires it fitted")
        symbol_matches = [
            symbol
            for symbol_reference, symbol in observed.component_symbols.items()
            if symbol_reference.casefold() == key
        ]
        if len(symbol_matches) != 1 or symbol_matches[0] != element.symbol:
            actual = symbol_matches[0] if len(symbol_matches) == 1 else "<unknown>"
            issues.append(f"{reference} symbol is {actual}; expected {element.symbol}")
        if component.footprint != element.footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {element.footprint}"
            )

        inventory_matches = [
            numbers
            for inventory_reference, numbers in observed.component_pin_numbers.items()
            if inventory_reference.casefold() == key
        ]
        if len(inventory_matches) != 1:
            issues.append(
                f"{reference} native pin inventory is "
                + ("missing" if not inventory_matches else "ambiguous")
            )
        else:
            known_numbers = {str(number).casefold() for number in inventory_matches[0]}
            expected_numbers = {
                assignment.pin.rsplit(".", 1)[1].casefold()
                for assignment in element.pin_assignments
            }
            missing_numbers = expected_numbers - known_numbers
            if missing_numbers:
                issues.append(
                    f"{reference} native pin inventory omits mapped pin(s): "
                    + ", ".join(sorted(missing_numbers))
                )

        for assignment in element.pin_assignments:
            assigned = pin_nets.get(assignment.pin.casefold(), set())
            if assigned != {assignment.net}:
                actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
                issues.append(
                    f"{assignment.pin} is assigned to {actual}; expected only {assignment.net}"
                )

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        detail=(
            "; ".join(issues)
            if issues
            else (
                f"The authored connector-to-board VBUS map contains "
                f"{len(requirement.elements)} exact component boundary/boundaries and matches "
                "the native symbol, footprint, pin inventory, and pin-to-net evidence."
            )
        ),
    )


def usb_c_vbus_capacitance_check(
    requirement: UsbCVbusCapacitanceRequirement,
    *,
    vbus_net: str,
    ground_net: str,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Compare mapped nominal port-side capacitance with project-authored limits."""
    issues: list[str] = []
    expected_nets = {vbus_net.casefold(), ground_net.casefold()}
    if len(expected_nets) != 2:
        return ElectricalCheck(
            id=check_id,
            status="FAIL",
            detail="The authored VBUS and ground nets are not distinct.",
        )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    mapped_references = {item.reference.casefold() for item in requirement.capacitors}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    component_index: dict[str, list[tuple[str, ComponentContract]]] = {}
    for reference, component in observed.components.items():
        component_index.setdefault(reference.casefold(), []).append((reference, component))
    symbol_index: dict[str, list[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        symbol_index.setdefault(reference.casefold(), []).append(symbol)
    inventory_index: dict[str, list[tuple[str, ...]]] = {}
    for reference, numbers in observed.component_pin_numbers.items():
        inventory_index.setdefault(reference.casefold(), []).append(
            tuple(str(number) for number in numbers)
        )

    total_pf = Decimal(0)
    complete_values = True
    for capacitor in requirement.capacitors:
        key = capacitor.reference.casefold()
        matches = component_index.get(key, [])
        if len(matches) != 1:
            issues.append(
                f"{capacitor.reference} is "
                + ("absent" if not matches else "ambiguous")
                + " in the native netlist"
            )
            complete_values = False
            continue
        reference, component = matches[0]
        if key in dnp:
            issues.append(f"{reference} is DNP but the VBUS capacitance map requires it fitted")

        symbols = symbol_index.get(key, [])
        if len(symbols) != 1 or symbols[0] != capacitor.symbol:
            actual = symbols[0] if len(symbols) == 1 else "<unknown>"
            issues.append(f"{reference} symbol is {actual}; expected {capacitor.symbol}")
        if component.footprint != capacitor.footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {capacitor.footprint}"
            )

        inventories = inventory_index.get(key, [])
        expected_pins = {item.pin.rsplit(".", 1)[1].casefold() for item in capacitor.pins}
        if len(inventories) != 1:
            issues.append(
                f"{reference} native pin inventory is "
                + ("missing" if not inventories else "ambiguous")
            )
        else:
            actual_pins = {number.casefold() for number in inventories[0]}
            if actual_pins != expected_pins:
                issues.append(
                    f"{reference} native pin inventory is {sorted(actual_pins)}; "
                    f"expected {sorted(expected_pins)}"
                )

        assigned_nets: set[str] = set()
        for assignment in capacitor.pins:
            expected_net = assignment.net.casefold()
            if expected_net not in expected_nets:
                issues.append(
                    f"{assignment.pin} maps to {assignment.net}; expected the port VBUS or ground net"
                )
            actual = pin_nets.get(assignment.pin.casefold(), set())
            if actual != {assignment.net}:
                rendered = ", ".join(sorted(actual)) if actual else "unconnected"
                issues.append(
                    f"{assignment.pin} is assigned to {rendered}; expected only {assignment.net}"
                )
            assigned_nets.update(net.casefold() for net in actual)
        if assigned_nets != expected_nets:
            issues.append(f"{reference} does not span exactly {vbus_net} and {ground_net}")

        capacitance_pf = parse_capacitance_pf(component.value)
        if capacitance_pf is None:
            issues.append(f"{reference} value {component.value!r} is not a supported capacitance")
            complete_values = False
        else:
            total_pf += capacitance_pf

    for key, matches in sorted(component_index.items()):
        if key in mapped_references or key in dnp or len(matches) != 1:
            continue
        reference, _component = matches[0]
        symbols = symbol_index.get(key, [])
        symbol_suggests_capacitor = len(symbols) == 1 and (
            "capacitor" in symbols[0].rsplit(":", 1)[-1].casefold()
            or symbols[0].rsplit(":", 1)[-1].casefold() in {"c", "cp"}
            or symbols[0].rsplit(":", 1)[-1].casefold().startswith(("c_", "cp_"))
        )
        reference_suggests_capacitor = key.startswith(("c", "cp"))
        if not (symbol_suggests_capacitor or reference_suggests_capacitor):
            continue
        inventories = inventory_index.get(key, [])
        relevant_assigned_pins = [
            pin
            for pin, nets in pin_nets.items()
            if pin.rsplit(".", 1)[0] == key
            and any(net.casefold() == vbus_net.casefold() for net in nets)
        ]
        if not relevant_assigned_pins:
            continue
        if len(inventories) != 1:
            issues.append(
                f"Unmapped capacitor candidate {reference} touches the port VBUS net "
                "but its native pin inventory is unavailable"
            )
            continue
        if len(inventories[0]) != 2:
            issues.append(
                f"Unmapped capacitor candidate {reference} touches the port VBUS net "
                "but is not a two-pin component"
            )
            continue
        issues.append(
            f"Unmapped capacitor candidate {reference} touches the port VBUS net; "
            "include it in the reviewed capacitance inventory"
        )

    total_nf = total_pf / Decimal(1000)
    minimum_nf = Decimal(str(requirement.minimum_nf))
    maximum_nf = Decimal(str(requirement.maximum_nf))
    total_text = format(total_nf.normalize(), "f")
    minimum_text = format(minimum_nf.normalize(), "f")
    maximum_text = format(maximum_nf.normalize(), "f")
    if complete_values and not minimum_nf <= total_nf <= maximum_nf:
        issues.append(
            f"Mapped nominal total is {total_text} nF; expected {minimum_text}–{maximum_text} nF"
        )

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=float(total_nf) if complete_values else None,
        unit="nF",
        detail=(
            "; ".join(issues)
            if issues
            else (
                f"Mapped nominal total {total_text} nF is within the "
                f"project-authored {minimum_text}–{maximum_text} nF range "
                f"({requirement.basis})."
            )
        ),
    )
