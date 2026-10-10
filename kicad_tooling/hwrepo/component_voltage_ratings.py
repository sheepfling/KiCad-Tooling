"""Compare authored component voltage ratings against reviewed stress envelopes."""

from __future__ import annotations

from .component_rating_models import ComponentVoltageRatingAnalysis
from .models import ElectricalCheck, NetlistContract


def component_voltage_rating_checks(
    spec: ComponentVoltageRatingAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare ratings only when exact native component and pin evidence match."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)
    components = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    checks: list[ElectricalCheck] = []
    for requirement in spec.requirements:
        base = f"component-voltage-rating/{requirement.id}"
        reference_key = requirement.reference.casefold()
        component = components.get(reference_key)
        identity_issues: list[str] = []
        if component is None:
            identity_issues.append(f"{requirement.reference} is absent from the native netlist")
        else:
            if reference_key in dnp:
                identity_issues.append(f"{requirement.reference} is marked DNP")
            actual_symbol = symbols.get(reference_key)
            if actual_symbol != requirement.expected_symbol:
                identity_issues.append(
                    f"symbol is {actual_symbol or 'unknown'}; expected {requirement.expected_symbol}"
                )
            if component.footprint != requirement.expected_footprint:
                identity_issues.append(
                    f"footprint is {component.footprint or 'empty'}; "
                    f"expected {requirement.expected_footprint}"
                )
            if component.part_id != requirement.expected_part_id:
                identity_issues.append(
                    f"PART_ID is {component.part_id or 'missing'}; "
                    f"expected {requirement.expected_part_id}"
                )
            expected_numbers = {
                pin.rsplit(".", maxsplit=1)[1].casefold() for pin in requirement.pins
            }
            actual_numbers = pin_numbers.get(reference_key)
            if actual_numbers != expected_numbers:
                identity_issues.append(
                    f"native pin inventory is {', '.join(sorted(actual_numbers or ())) or 'unknown'}; "
                    f"expected {', '.join(sorted(expected_numbers))}"
                )
        identity_ok = not identity_issues
        checks.append(
            ElectricalCheck(
                id=f"{base}/identity",
                status="PASS" if identity_ok else "FAIL",
                detail=(
                    f"{requirement.reference} matches the reviewed symbol, footprint, part ID, "
                    "population, and two-pin inventory."
                    if identity_ok
                    else f"{requirement.reference}: {'; '.join(identity_issues)}."
                ),
            )
        )

        pins_ok = True
        for index, (pin, expected_net) in enumerate(
            zip(requirement.pins, requirement.nets, strict=True), start=1
        ):
            pin_key = pin.casefold()
            actual_nets = pin_nets.get(pin_key, set())
            if pin_key not in known_pins:
                detail = f"{pin} is absent from the native symbol pin inventory"
                pin_ok = False
            elif actual_nets != {expected_net}:
                assigned = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
                detail = f"{pin} is assigned to {assigned}; expected {expected_net}"
                pin_ok = False
            else:
                detail = f"{pin} is assigned to the reviewed net {expected_net}"
                pin_ok = True
            pins_ok = pins_ok and pin_ok
            checks.append(
                ElectricalCheck(
                    id=f"{base}/pin-{index}",
                    status="PASS" if pin_ok else "FAIL",
                    detail=detail,
                )
            )

        if identity_ok and pins_ok:
            utilization = (
                requirement.maximum_expected_voltage_v / requirement.rated_working_voltage_v
            )
            passed = utilization <= requirement.maximum_utilization_fraction
            checks.append(
                ElectricalCheck(
                    id=f"{base}/utilization",
                    status="PASS" if passed else "FAIL",
                    detail=(
                        f"{requirement.maximum_expected_voltage_v:g} V maximum expected stress "
                        f"uses {utilization:.6g} of the {requirement.rated_working_voltage_v:g} V "
                        f"working rating; project limit is "
                        f"{requirement.maximum_utilization_fraction:.6g}. "
                        f"Rating: {requirement.rating_source} ({requirement.rating_conditions}). "
                        f"Stress basis: {requirement.stress_basis}."
                    ),
                    observed=utilization,
                    unit="fraction",
                )
            )
        else:
            checks.append(
                ElectricalCheck(
                    id=f"{base}/utilization",
                    status="NOT_APPLICABLE",
                    detail=(
                        "Voltage utilization was not compared because the exact native component "
                        "identity or pin/net map does not match the reviewed requirement."
                    ),
                )
            )
    return tuple(checks)
