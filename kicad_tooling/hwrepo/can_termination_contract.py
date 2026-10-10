"""Can termination contract for deterministic KiCad bus analysis."""

from __future__ import annotations

from .can_termination_models import (
    CanTerminationAnalysis,
    CanTerminationMidpointCapacitorRequirement,
)
from .crystal_networks import parse_capacitance_pf
from .models import ElectricalCheck, NetlistContract
from .resistor_paths import (
    RESISTOR_REFERENCE_PATTERN,
    direct_resistors,
    resistance_ohms,
)


def can_termination_checks(
    spec: CanTerminationAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare exact authored CAN termination paths with a native netlist."""
    resistors = direct_resistors(observed)
    resistors_by_reference = {item.reference.casefold(): item for item in resistors}
    components = {
        reference.casefold(): (reference, item) for reference, item in observed.components.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    component_pins: dict[str, set[str]] = {}
    for pin in set(observed.pin_functions) | set(pin_nets):
        component_pins.setdefault(pin.rsplit(".", 1)[0].casefold(), set()).add(pin)
    known_pins = set(observed.pin_functions) | set(pin_nets)
    known_pins.update(
        f"{reference}.{number}"
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    )

    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        pin_failures: list[str] = []
        for label, required_net, pins in (
            ("CANH", bus.high_net, bus.high_pins),
            ("CANL", bus.low_net, bus.low_pins),
        ):
            for pin in pins:
                if pin not in known_pins:
                    pin_failures.append(
                        f"{label} pin {pin} is absent from the native symbol pin inventory"
                    )
                    continue
                assigned = pin_nets.get(pin, set())
                if assigned != {required_net}:
                    nets = ", ".join(sorted(assigned)) if assigned else "unconnected"
                    pin_failures.append(
                        f"{label} pin {pin} is assigned to {nets}; expected {required_net}"
                    )
        results.append(
            ElectricalCheck(
                id=f"can-termination/{bus.id}/signal-pins",
                status="FAIL" if pin_failures else "PASS",
                detail=(
                    "; ".join(pin_failures)
                    if pin_failures
                    else f"Declared CANH/CANL pins are assigned to {bus.high_net}/{bus.low_net}."
                ),
            )
        )
        expected_direct = {
            resistor.reference.casefold()
            for endpoint in bus.endpoints
            if endpoint.topology == "direct"
            for resistor in endpoint.resistors
        }
        actual_direct = tuple(
            item
            for item in resistors
            if {item.first_net, item.second_net} == {bus.high_net, bus.low_net}
        )
        unlisted_direct = tuple(
            item for item in actual_direct if item.reference.casefold() not in expected_direct
        )
        results.append(
            ElectricalCheck(
                id=f"can-termination/{bus.id}/unlisted-direct",
                status="FAIL" if unlisted_direct else "PASS",
                detail=(
                    "Unlisted direct resistors across the declared CAN nets: "
                    + ", ".join(
                        f"{item.reference}={item.resistance_ohms:g}Ω" for item in unlisted_direct
                    )
                    if unlisted_direct
                    else f"No unlisted direct resistor across {bus.high_net} and {bus.low_net}."
                ),
            )
        )
        for endpoint in bus.endpoints:
            base_id = f"can-termination/{bus.id}/{endpoint.id}"
            if endpoint.topology == "external":
                results.append(
                    ElectricalCheck(
                        id=f"{base_id}/external-evidence",
                        status="NOT_APPLICABLE",
                        detail=(
                            f"External termination is explicitly declared for endpoint {endpoint.id}: "
                            f"{endpoint.basis}. A schematic netlist cannot verify remote hardware."
                        ),
                    )
                )
                if endpoint.expected_dnp_resistors:
                    failures: list[str] = []
                    for reference in endpoint.expected_dnp_resistors:
                        key = reference.casefold()
                        component_entry = components.get(key)
                        if component_entry is None:
                            failures.append(f"{reference} is absent from the netlist")
                            continue
                        _, component = component_entry
                        if key not in dnp:
                            failures.append(f"{reference} is fitted, expected DNP")
                        if RESISTOR_REFERENCE_PATTERN.fullmatch(reference) is None:
                            failures.append(f"{reference} is not a recognized resistor reference")
                        value = resistance_ohms(component.value)
                        if value is None or value <= 0:
                            failures.append(
                                f"{reference} has no recognized positive resistor value"
                            )
                        pins = component_pins.get(key, set())
                        assigned_nets = [pin_nets.get(pin, set()) for pin in pins]
                        known_pin_numbers = observed.component_pin_numbers.get(component_entry[0])
                        if (
                            len(pins) != 2
                            or (known_pin_numbers is not None and len(known_pin_numbers) != 2)
                            or any(len(nets) != 1 for nets in assigned_nets)
                            or {next(iter(nets)) for nets in assigned_nets if len(nets) == 1}
                            != {bus.high_net, bus.low_net}
                        ):
                            failures.append(
                                f"{reference} does not map exactly across {bus.high_net}/{bus.low_net}"
                            )
                    results.append(
                        ElectricalCheck(
                            id=f"{base_id}/dnp-options",
                            status="FAIL" if failures else "PASS",
                            detail=(
                                "; ".join(failures)
                                if failures
                                else "Expected DNP termination option(s) are present across the declared CAN nets: "
                                + ", ".join(endpoint.expected_dnp_resistors)
                                + "."
                            ),
                        )
                    )
                continue

            path_details: list[str] = []
            failures = []
            observed_total = 0.0
            for requirement in endpoint.resistors:
                resistor = resistors_by_reference.get(requirement.reference.casefold())
                if resistor is None:
                    if requirement.reference.casefold() in dnp:
                        failures.append(f"{requirement.reference} is DNP but must be fitted")
                    elif requirement.reference.casefold() not in components:
                        failures.append(f"{requirement.reference} is absent from the netlist")
                    else:
                        failures.append(
                            f"{requirement.reference} is not a recognized fitted two-terminal resistor"
                        )
                    continue
                observed_total += resistor.resistance_ohms
                actual_path = {resistor.first_net, resistor.second_net}
                expected_path = {requirement.first_net, requirement.second_net}
                if actual_path != expected_path:
                    failures.append(
                        f"{requirement.reference} connects {resistor.first_net}/{resistor.second_net}, "
                        f"expected {requirement.first_net}/{requirement.second_net}"
                    )
                if (
                    not requirement.minimum_ohms
                    <= resistor.resistance_ohms
                    <= requirement.maximum_ohms
                ):
                    failures.append(
                        f"{requirement.reference} is {resistor.resistance_ohms:g}Ω, outside "
                        f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
                    )
                path_details.append(
                    f"{resistor.reference}={resistor.resistance_ohms:g}Ω "
                    f"({requirement.first_net}/{requirement.second_net})"
                )
            results.append(
                ElectricalCheck(
                    id=base_id,
                    status="FAIL" if failures else "PASS",
                    observed=observed_total
                    if len(path_details) == len(endpoint.resistors)
                    else None,
                    unit="Ω",
                    detail=(
                        f"{endpoint.topology} termination at {endpoint.id} on "
                        f"{bus.high_net}/{bus.low_net}: "
                        + ("; ".join(failures) if failures else ", ".join(path_details))
                        + "."
                    ),
                )
            )
            if endpoint.midpoint_capacitor is not None:
                assert endpoint.midpoint_net is not None
                results.append(
                    _can_midpoint_capacitor_check(
                        endpoint.midpoint_capacitor,
                        endpoint.midpoint_net,
                        observed,
                        f"{base_id}/midpoint-capacitor",
                    )
                )
    return tuple(results)


def _can_midpoint_capacitor_check(
    requirement: CanTerminationMidpointCapacitorRequirement,
    midpoint_net: str,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Check one explicitly mapped capacitor and its exact two native pin nets."""
    issues: list[str] = []
    reference_key = requirement.reference.casefold()
    component_matches = [
        (reference, component)
        for reference, component in observed.components.items()
        if reference.casefold() == reference_key
    ]
    if len(component_matches) != 1:
        issues.append(
            f"{requirement.reference} is "
            + ("absent" if not component_matches else "ambiguous")
            + " in the native netlist"
        )
        component = None
    else:
        _, component = component_matches[0]

    symbols = [
        symbol
        for reference, symbol in observed.component_symbols.items()
        if reference.casefold() == reference_key
    ]
    if len(symbols) != 1 or symbols[0] != requirement.expected_symbol:
        actual = symbols[0] if len(symbols) == 1 else "<unknown>"
        issues.append(
            f"{requirement.reference} symbol is {actual}; expected {requirement.expected_symbol}"
        )

    if component is not None:
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {requirement.expected_footprint}"
            )
        if reference_key in {item.casefold() for item in observed.dnp_components}:
            issues.append(f"{requirement.reference} is DNP but must be fitted")
        capacitance_pf = parse_capacitance_pf(component.value)
        if capacitance_pf is None:
            issues.append(f"{requirement.reference} has no recognized positive capacitance value")
        elif not (
            requirement.minimum_nominal_capacitance_pf
            <= capacitance_pf
            <= requirement.maximum_nominal_capacitance_pf
        ):
            issues.append(
                f"{requirement.reference} is {capacitance_pf:g}pF, outside "
                f"{requirement.minimum_nominal_capacitance_pf:g}–"
                f"{requirement.maximum_nominal_capacitance_pf:g}pF"
            )
    else:
        capacitance_pf = None

    inventory_matches = [
        numbers
        for reference, numbers in observed.component_pin_numbers.items()
        if reference.casefold() == reference_key
    ]
    expected_pins = {requirement.midpoint_pin.casefold(), requirement.reference_pin.casefold()}
    if len(inventory_matches) != 1:
        issues.append(
            f"{requirement.reference} native pin inventory is "
            + ("missing" if not inventory_matches else "ambiguous")
        )
    else:
        pin_numbers = {str(number).casefold() for number in inventory_matches[0]}
        expected_numbers = {
            requirement.midpoint_pin.rsplit(".", 1)[1].casefold(),
            requirement.reference_pin.rsplit(".", 1)[1].casefold(),
        }
        if len(pin_numbers) != 2 or pin_numbers != expected_numbers:
            issues.append(
                f"{requirement.reference} native pin inventory is "
                f"{', '.join(sorted(pin_numbers)) or '<empty>'}; expected exactly "
                f"{', '.join(sorted(expected_numbers))}"
            )

    native_pins = {
        pin.casefold()
        for pin in set(observed.pin_functions)
        | {pin for pins in observed.nets.values() for pin in pins}
        if pin.rsplit(".", 1)[0].casefold() == reference_key
    }
    extra_pins = native_pins - expected_pins
    if extra_pins:
        issues.append(
            f"{requirement.reference} has unexpected mapped pins: " + ", ".join(sorted(extra_pins))
        )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    for pin, expected_net in (
        (requirement.midpoint_pin, midpoint_net),
        (requirement.reference_pin, requirement.reference_net),
    ):
        assigned = pin_nets.get(pin.casefold(), set())
        if assigned != {expected_net}:
            actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
            issues.append(f"{pin} is assigned to {actual}; expected only {expected_net}")

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=None if capacitance_pf is None else float(capacitance_pf),
        unit="pF",
        detail=(
            "; ".join(issues)
            if issues
            else f"{requirement.reference}={capacitance_pf:g}pF maps "
            f"{requirement.midpoint_pin} to {midpoint_net} and "
            f"{requirement.reference_pin} to {requirement.reference_net}."
        ),
    )
