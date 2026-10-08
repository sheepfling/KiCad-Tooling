"""Compare project-authored per-contact current with exact connector ratings."""

from __future__ import annotations

from .models import ConnectorContactRatingAnalysis, ElectricalCheck, NetlistContract


def connector_contact_rating_checks(
    spec: ConnectorContactRatingAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Check contact current only when native identity and pin mapping match."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    pin_functions = {
        pin.casefold(): function.casefold() for pin, function in observed.pin_functions.items()
    }
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
        base = f"connector-contact-rating/{requirement.id}"
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
            expected_numbers = {pin.casefold() for pin in requirement.native_pin_numbers}
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
                    f"{requirement.reference} matches the reviewed symbol, footprint, PART_ID, "
                    "population, and complete native pin inventory."
                    if identity_ok
                    else f"{requirement.reference}: {'; '.join(identity_issues)}."
                ),
            )
        )

        for contact in requirement.contacts:
            pin = f"{requirement.reference}.{contact.pin_number}"
            pin_key = pin.casefold()
            assignment_issues: list[str] = []
            if pin_key not in known_pins:
                assignment_issues.append(f"{pin} is absent from the native pin inventory")
            actual_function = pin_functions.get(pin_key)
            if actual_function != contact.expected_function.casefold():
                assignment_issues.append(
                    f"pin function is {actual_function or 'unknown'}; "
                    f"expected {contact.expected_function}"
                )
            actual_nets = pin_nets.get(pin_key, set())
            if actual_nets != {contact.expected_net}:
                assigned = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
                assignment_issues.append(
                    f"net assignment is {assigned}; expected {contact.expected_net}"
                )

            assignment_ok = not assignment_issues
            checks.append(
                ElectricalCheck(
                    id=f"{base}/contact-{contact.id}/assignment",
                    status="PASS" if assignment_ok else "FAIL",
                    detail=(
                        f"{pin} has the reviewed {contact.expected_function} function on "
                        f"{contact.expected_net}."
                        if assignment_ok
                        else f"{pin}: {'; '.join(assignment_issues)}."
                    ),
                )
            )

            current_id = f"{base}/contact-{contact.id}/utilization"
            if identity_ok and assignment_ok:
                utilization = (
                    contact.maximum_expected_current_a / contact.derated_allowable_current_a
                )
                passed = utilization <= contact.maximum_utilization_fraction
                checks.append(
                    ElectricalCheck(
                        id=current_id,
                        status="PASS" if passed else "FAIL",
                        detail=(
                            f"{contact.maximum_expected_current_a:g} A maximum expected current on "
                            f"{pin} uses {utilization:.6g} of the "
                            f"{contact.derated_allowable_current_a:g} A reviewed allowable "
                            f"contact current; project limit is "
                            f"{contact.maximum_utilization_fraction:.6g}. Source rating: "
                            f"{contact.rated_current_a:g} A from {contact.rating_source} "
                            f"({contact.rating_conditions}). Derating basis: "
                            f"{contact.derating_basis}. Load basis: {contact.load_basis}."
                        ),
                        observed=utilization,
                        unit="fraction",
                    )
                )
            else:
                checks.append(
                    ElectricalCheck(
                        id=current_id,
                        status="NOT_APPLICABLE",
                        detail=(
                            "Contact current was not compared because the exact native connector "
                            "identity or pin/function/net assignment does not match the reviewed "
                            "requirement."
                        ),
                    )
                )
    return tuple(checks)
