"""I2c pullup contract paths for deterministic KiCad bus analysis."""

from __future__ import annotations

from .i2c_pullup_models import I2cPullupSeriesPathRequirement
from .models import ElectricalCheck, NetlistContract
from .resistor_paths import DirectResistor


def i2c_series_path_check(
    path: I2cPullupSeriesPathRequirement,
    observed: NetlistContract,
    resistors: tuple[DirectResistor, ...],
    check_id: str,
) -> tuple[ElectricalCheck, float | None]:
    """Check one authored resistor chain and its branch-free native junctions."""
    issues: list[str] = []
    total_ohms = 0.0
    pin_for_net_by_reference: dict[str, dict[str, str]] = {}
    resistor_by_reference: dict[str, list[DirectResistor]] = {}
    for resistor in resistors:
        resistor_by_reference.setdefault(resistor.reference.casefold(), []).append(resistor)

    for requirement in path.resistors:
        reference_key = requirement.reference.casefold()
        components = [
            (reference, component)
            for reference, component in observed.components.items()
            if reference.casefold() == reference_key
        ]
        if len(components) != 1:
            issues.append(
                f"{requirement.reference} is "
                + ("absent" if not components else "ambiguous")
                + " in the native netlist"
            )
            component_reference = requirement.reference
            component = None
        else:
            component_reference, component = components[0]

        symbols = [
            symbol
            for reference, symbol in observed.component_symbols.items()
            if reference.casefold() == reference_key
        ]
        if len(symbols) != 1 or symbols[0] != requirement.expected_symbol:
            actual_symbol = symbols[0] if len(symbols) == 1 else "<unknown>"
            issues.append(
                f"{requirement.reference} symbol is {actual_symbol}; "
                f"expected {requirement.expected_symbol}"
            )
        if component is not None:
            if component.footprint != requirement.expected_footprint:
                issues.append(
                    f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                    f"expected {requirement.expected_footprint}"
                )
            if reference_key in {item.casefold() for item in observed.dnp_components}:
                issues.append(f"{requirement.reference} is DNP but the pull-up is required")

        actual_matches = resistor_by_reference.get(reference_key, [])
        if len(actual_matches) != 1:
            issues.append(
                f"{requirement.reference} is "
                + (
                    "not a recognized fitted two-terminal resistor"
                    if actual_matches
                    else "missing or not a recognized fitted two-terminal resistor"
                )
            )
        else:
            actual = actual_matches[0]
            actual_path = {actual.first_net, actual.second_net}
            if actual_path != {requirement.from_net, requirement.to_net}:
                issues.append(
                    f"{requirement.reference} connects {actual.first_net}/{actual.second_net}; "
                    f"expected {requirement.from_net}/{requirement.to_net}"
                )
            if not requirement.minimum_ohms <= actual.resistance_ohms <= requirement.maximum_ohms:
                issues.append(
                    f"{requirement.reference} is {actual.resistance_ohms:g}Ω, outside "
                    f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
                )
            total_ohms += actual.resistance_ohms

        inventories = [
            tuple(numbers)
            for reference, numbers in observed.component_pin_numbers.items()
            if reference.casefold() == reference_key
        ]
        if len(inventories) != 1:
            issues.append(
                f"{requirement.reference} native pin inventory is "
                + ("missing" if not inventories else "ambiguous")
            )
            continue
        pin_numbers = tuple(dict.fromkeys(str(number) for number in inventories[0]))
        if len(pin_numbers) != 2:
            issues.append(
                f"{requirement.reference} native pin inventory has {len(pin_numbers)} unique pins; "
                "expected exactly two"
            )
            continue

        pin_for_net: dict[str, str] = {}
        for number in pin_numbers:
            pin = f"{component_reference}.{number}"
            assigned = {
                net
                for net, pins in observed.nets.items()
                if any(candidate.casefold() == pin.casefold() for candidate in pins)
            }
            if len(assigned) != 1:
                actual_nets = ", ".join(sorted(assigned)) or "unconnected"
                issues.append(
                    f"{pin} is assigned to {actual_nets}; each series resistor pin must have one net"
                )
                continue
            net = next(iter(assigned))
            if net not in {requirement.from_net, requirement.to_net}:
                issues.append(
                    f"{pin} is assigned to {net}; expected {requirement.from_net} or "
                    f"{requirement.to_net}"
                )
            elif net in pin_for_net:
                issues.append(f"{requirement.reference} has multiple pins on {net}")
            else:
                pin_for_net[net] = pin
        if set(pin_for_net) != {requirement.from_net, requirement.to_net}:
            issues.append(
                f"{requirement.reference} does not assign exactly one native pin to each "
                f"of {requirement.from_net}/{requirement.to_net}"
            )
        pin_for_net_by_reference[reference_key] = pin_for_net

    for first, second in zip(path.resistors, path.resistors[1:], strict=False):
        junction = first.to_net
        first_pins = pin_for_net_by_reference.get(first.reference.casefold(), {})
        second_pins = pin_for_net_by_reference.get(second.reference.casefold(), {})
        expected = {first_pins.get(junction), second_pins.get(junction)}
        expected.discard(None)
        actual = {pin.casefold() for pin in observed.nets.get(junction, ())}
        expected_normalized = {pin.casefold() for pin in expected if pin is not None}
        if actual != expected_normalized:
            observed_pins = ", ".join(sorted(actual)) or "no pins"
            expected_display = (
                ", ".join(sorted(expected_normalized)) or "the two mapped resistor pins"
            )
            issues.append(
                f"series junction {junction} contains {observed_pins}; expected only "
                f"{expected_display}"
            )

    result = ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=total_ohms if not issues else None,
        unit="Ω",
        detail=(
            "; ".join(issues)
            if issues
            else f"{' + '.join(item.reference for item in path.resistors)}="
            f"{total_ohms:g}Ω forms the declared unbranched path "
            f"{path.signal_net} to {path.rail_net}."
        ),
    )
    return result, total_ohms if not issues else None
