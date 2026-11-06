"""Compare exact native capacitor evidence with authored hold-up envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .capacitance_values import parse_capacitance_pf
from .electrical_report_models import ElectricalCheck
from .energy_storage_models import EnergyStorageAnalysis, EnergyStorageHoldUpRequirement
from .netlist_contract_models import ComponentContract, NetlistContract

_PICO_FARADS_PER_FARAD = Decimal("1e12")


def energy_storage_hold_up_checks(
    spec: EnergyStorageAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Check mapped component identity, exact net assignments, and hold-up margin."""
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
        checks.extend(
            _requirement_checks(
                requirement, components, symbols, pin_numbers, dnp, known_pins, pin_nets
            )
        )
    return tuple(checks)


def _requirement_checks(
    requirement: EnergyStorageHoldUpRequirement,
    components: Mapping[str, ComponentContract],
    symbols: Mapping[str, str],
    pin_numbers: Mapping[str, set[str]],
    dnp: set[str],
    known_pins: set[str],
    pin_nets: Mapping[str, set[str]],
) -> tuple[ElectricalCheck, ...]:
    prefix = f"energy-storage/{requirement.id}"
    reference = requirement.reference
    key = reference.casefold()
    component = components.get(key)
    identity_issues: list[str] = []
    if component is None:
        identity_issues.append(f"{reference} is absent from the native netlist")
    else:
        if key in dnp:
            identity_issues.append(f"{reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != requirement.expected_symbol:
            identity_issues.append(
                f"symbol is {actual_symbol or 'unknown'}; expected {requirement.expected_symbol}"
            )
        if component.footprint != requirement.expected_footprint:
            identity_issues.append(
                f"footprint is {component.footprint or 'empty'}; expected {requirement.expected_footprint}"
            )
        if component.part_id != requirement.expected_part_id:
            identity_issues.append(
                f"PART_ID is {component.part_id or 'missing'}; expected {requirement.expected_part_id}"
            )
        expected_numbers = {pin.rsplit(".", 1)[1].casefold() for pin in requirement.pins}
        actual_numbers = pin_numbers.get(key)
        if actual_numbers != expected_numbers:
            identity_issues.append(
                f"native pin inventory is {', '.join(sorted(actual_numbers or ())) or 'unknown'}; "
                f"expected {', '.join(sorted(expected_numbers))}"
            )
    identity_ok = not identity_issues
    checks = [
        ElectricalCheck(
            id=f"{prefix}/identity",
            status="PASS" if identity_ok else "FAIL",
            detail=(
                f"{reference} matches the reviewed symbol, footprint, part ID, population, and pin inventory."
                if identity_ok
                else f"{reference}: {'; '.join(identity_issues)}."
            ),
        )
    ]
    pins_ok = True
    for index, (pin, expected_net) in enumerate(
        zip(requirement.pins, requirement.nets, strict=True), 1
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
                id=f"{prefix}/pin-{index}", status="PASS" if pin_ok else "FAIL", detail=detail
            )
        )

    if not identity_ok or not pins_ok or component is None:
        checks.append(
            ElectricalCheck(
                id=f"{prefix}/hold-up",
                status="NOT_APPLICABLE",
                detail="Hold-up is not compared until exact fitted component identity and both pin/net assignments match.",
            )
        )
        return tuple(checks)

    nominal_pf = parse_capacitance_pf(component.value)
    if nominal_pf is None:
        checks.append(
            ElectricalCheck(
                id=f"{prefix}/hold-up",
                status="FAIL",
                detail=f"{reference} value {component.value!r} is not a supported explicit capacitance.",
            )
        )
        return tuple(checks)
    nominal_f = nominal_pf / _PICO_FARADS_PER_FARAD
    effective_f = nominal_f * Decimal(str(requirement.minimum_effective_capacitance_fraction))
    voltage_window = Decimal(str(requirement.minimum_start_voltage_v)) - Decimal(
        str(requirement.minimum_operating_voltage_v)
    )
    current_a = Decimal(str(requirement.maximum_constant_load_current_a))
    required_time_s = Decimal(str(requirement.minimum_hold_up_time_s))
    required_f = current_a * required_time_s / voltage_window
    utilization = required_f / effective_f
    maximum_utilization = Decimal(str(requirement.maximum_utilization_fraction))
    passed = utilization <= maximum_utilization
    checks.append(
        ElectricalCheck(
            id=f"{prefix}/hold-up",
            status="PASS" if passed else "FAIL",
            observed=float(utilization),
            unit="fraction",
            detail=(
                f"{reference} nominal capacitance is {nominal_f} F; project-reviewed effective "
                f"fraction {requirement.minimum_effective_capacitance_fraction} from "
                f"{requirement.effective_capacitance_basis} gives {effective_f} F. "
                f"The constant-current model requires {required_f} F for {required_time_s} s at "
                f"{current_a} A across {voltage_window} V ({requirement.load_current_basis}; "
                f"{requirement.voltage_window_basis}; {requirement.hold_up_basis}). "
                f"Utilization is {utilization}; maximum is {maximum_utilization}."
            ),
        )
    )
    return tuple(checks)
