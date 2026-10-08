"""Deterministic checks for explicitly mapped regulator feedback dividers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TypeVar

from .bus_heuristics import direct_resistors, resistance_ohms
from .models import (
    NetlistContract,
    RegulatorFeedbackCoverageEntry,
    RegulatorFeedbackCoverageReport,
    RegulatorFeedbackMap,
    RegulatorFeedbackRequirement,
)

_Value = TypeVar("_Value")


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _pin_nets(observed: NetlistContract) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            result.setdefault(pin.casefold(), set()).add(net)
    return result


def _pin_inventory_contains(observed: NetlistContract, pin: str) -> bool | None:
    reference, separator, number = pin.rpartition(".")
    if not separator:
        return False
    inventory = _lookup(observed.component_pin_numbers, reference)
    if inventory is None:
        return None
    return any(str(candidate).casefold() == number.casefold() for candidate in inventory)


def _component_identity(
    observed: NetlistContract,
    reference: str,
    expected_value: str | None,
    expected_symbol: str,
    expected_footprint: str,
    issues: list[str],
) -> bool:
    component = _lookup(observed.components, reference)
    symbol = _lookup(observed.component_symbols, reference)
    if component is None:
        issues.append(f"Mapped component {reference} is missing or ambiguous in the native netlist")
        return False
    valid = True
    if expected_value is not None and component.value != expected_value:
        issues.append(f"{reference} value is {component.value}; expected {expected_value}")
        valid = False
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
        valid = False
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )
        valid = False
    return valid


def _entry(
    requirement: RegulatorFeedbackRequirement,
    observed: NetlistContract,
    pins_by_net: dict[str, set[str]],
    dnp_references: set[str],
) -> RegulatorFeedbackCoverageEntry:
    issues: list[str] = []
    identity_valid = _component_identity(
        observed,
        requirement.regulator_reference,
        requirement.expected_regulator_value,
        requirement.expected_regulator_symbol,
        requirement.expected_regulator_footprint,
        issues,
    )
    for resistor in (requirement.upper_resistor, requirement.lower_resistor):
        identity_valid = (
            _component_identity(
                observed,
                resistor.reference,
                None,
                resistor.expected_symbol,
                resistor.expected_footprint,
                issues,
            )
            and identity_valid
        )

    mapped_references = (
        requirement.regulator_reference,
        requirement.upper_resistor.reference,
        requirement.lower_resistor.reference,
    )
    dnp = tuple(
        reference for reference in mapped_references if reference.casefold() in dnp_references
    )
    if dnp:
        issues.append(
            f"Mapped regulator-divider components are marked not fitted: {', '.join(dnp)}"
        )
        identity_valid = False

    all_pins = (
        requirement.output_pin,
        requirement.feedback_pin,
        requirement.upper_resistor.rail_pin,
        requirement.upper_resistor.feedback_pin,
        requirement.lower_resistor.feedback_pin,
        requirement.lower_resistor.rail_pin,
    )
    observed_pin_nets: dict[str, tuple[str, ...]] = {}
    pin_evidence = {
        pin.casefold()
        for pin in (
            *observed.pin_functions,
            *observed.pin_electrical_types,
            *(item for net_pins in observed.nets.values() for item in net_pins),
        )
    }
    pins_valid = True
    for pin in all_pins:
        inventory = _pin_inventory_contains(observed, pin)
        if inventory is None:
            issues.append(f"{pin} has no native component-pin inventory")
            pins_valid = False
        elif not inventory:
            issues.append(f"{pin} is absent from the native component-pin inventory")
            pins_valid = False
        if pin.casefold() not in pin_evidence:
            issues.append(f"{pin} has no native pin evidence")
            pins_valid = False
        observed_pin_nets[pin] = tuple(sorted(pins_by_net.get(pin.casefold(), ())))

    for pin, expected_function in (
        (requirement.output_pin, requirement.expected_output_pin_function),
        (requirement.feedback_pin, requirement.expected_feedback_pin_function),
    ):
        observed_function = _lookup(observed.pin_functions, pin)
        if not isinstance(observed_function, str):
            issues.append(f"{pin} has no native symbol pin function")
            pins_valid = False
        elif observed_function.strip().casefold() != expected_function.strip().casefold():
            issues.append(f"{pin} function is {observed_function}; expected {expected_function}")
            pins_valid = False

    expected_fixed_nets = (
        (requirement.output_pin, requirement.output_net, "regulator output"),
        (requirement.upper_resistor.rail_pin, requirement.output_net, "upper-resistor output"),
        (
            requirement.lower_resistor.rail_pin,
            requirement.reference_net,
            "lower-resistor reference",
        ),
    )
    nets_valid = True
    for pin, expected_net, role in expected_fixed_nets:
        actual = observed_pin_nets[pin]
        if actual != (expected_net,):
            issues.append(
                f"{role} pin {pin} is on {', '.join(actual) or 'unconnected'}; "
                f"expected {expected_net}"
            )
            nets_valid = False

    feedback_pins = (
        requirement.feedback_pin,
        requirement.upper_resistor.feedback_pin,
        requirement.lower_resistor.feedback_pin,
    )
    feedback_assignments = [observed_pin_nets[pin] for pin in feedback_pins]
    feedback_net: str | None = None
    if (
        all(len(nets) == 1 for nets in feedback_assignments)
        and len({nets[0] for nets in feedback_assignments}) == 1
    ):
        feedback_net = feedback_assignments[0][0]
        if feedback_net.casefold() in {
            requirement.output_net.casefold(),
            requirement.reference_net.casefold(),
        }:
            issues.append("Regulator feedback node is shorted to the output or reference net")
            nets_valid = False
            feedback_net = None
    else:
        issues.append(
            "Regulator FB pin and both divider feedback pins must share one uniquely assigned net; "
            f"observed {feedback_assignments}"
        )
        nets_valid = False

    nominal_values: dict[str, float] = {}
    values_valid = True
    for resistor in (requirement.upper_resistor, requirement.lower_resistor):
        component = _lookup(observed.components, resistor.reference)
        parsed = None if component is None else resistance_ohms(component.value)
        if parsed is None or not math.isfinite(parsed) or parsed <= 0:
            issues.append(
                f"{resistor.reference} value {getattr(component, 'value', '<missing>')} "
                "is not a supported positive nominal resistance"
            )
            values_valid = False
            continue
        nominal_values[resistor.reference] = parsed
        if not (
            resistor.minimum_nominal_resistance_ohms
            <= parsed
            <= resistor.maximum_nominal_resistance_ohms
        ):
            issues.append(
                f"{resistor.reference} is {parsed:g} Ω; authored nominal range is "
                f"{resistor.minimum_nominal_resistance_ohms:g}–"
                f"{resistor.maximum_nominal_resistance_ohms:g} Ω"
            )

    mapped_resistors = {
        requirement.upper_resistor.reference.casefold(),
        requirement.lower_resistor.reference.casefold(),
    }
    extra_feedback_resistors = tuple(
        resistor.reference
        for resistor in direct_resistors(observed)
        if resistor.reference.casefold() not in mapped_resistors
        and feedback_net is not None
        and feedback_net in (resistor.first_net, resistor.second_net)
    )
    if extra_feedback_resistors:
        issues.append(
            "Unmapped fitted resistors touch the feedback node and may change its DC setpoint: "
            + ", ".join(extra_feedback_resistors)
        )
        nets_valid = False

    calculated_minimum: float | None = None
    calculated_maximum: float | None = None
    calculation_valid = True
    if identity_valid and pins_valid and nets_valid and values_valid and len(nominal_values) == 2:
        try:
            ratio = (
                1.0
                + nominal_values[requirement.upper_resistor.reference]
                / nominal_values[requirement.lower_resistor.reference]
            )
            minimum = requirement.minimum_feedback_reference_voltage_v * ratio
            maximum = requirement.maximum_feedback_reference_voltage_v * ratio
        except OverflowError:
            calculation_valid = False
        else:
            if not math.isfinite(minimum) or not math.isfinite(maximum):
                calculation_valid = False
            else:
                calculated_minimum = minimum
                calculated_maximum = maximum
                if (
                    calculated_minimum < requirement.minimum_target_output_voltage_v
                    or calculated_maximum > requirement.maximum_target_output_voltage_v
                ):
                    issues.append(
                        f"Calculated nominal output range {calculated_minimum:g}–"
                        f"{calculated_maximum:g} V is outside authored target "
                        f"{requirement.minimum_target_output_voltage_v:g}–"
                        f"{requirement.maximum_target_output_voltage_v:g} V"
                    )
        if not calculation_valid:
            issues.append(
                "Calculated nominal output range exceeds the supported finite numeric range"
            )

    value_out_of_range = any("authored nominal range" in issue for issue in issues)
    output_out_of_range = any("outside authored target" in issue for issue in issues)
    if (
        not identity_valid
        or not pins_valid
        or not nets_valid
        or not values_valid
        or not calculation_valid
    ):
        status = "INCOMPLETE"
    elif value_out_of_range or output_out_of_range:
        status = "OUT_OF_RANGE"
    else:
        status = "COMPLETE"

    return RegulatorFeedbackCoverageEntry(
        id=requirement.id,
        regulator_reference=requirement.regulator_reference,
        status=status,
        output_net=requirement.output_net,
        reference_net=requirement.reference_net,
        feedback_net=feedback_net,
        feedback_reference_minimum_v=requirement.minimum_feedback_reference_voltage_v,
        feedback_reference_maximum_v=requirement.maximum_feedback_reference_voltage_v,
        target_output_minimum_v=requirement.minimum_target_output_voltage_v,
        target_output_maximum_v=requirement.maximum_target_output_voltage_v,
        nominal_resistance_ohms=nominal_values,
        calculated_output_minimum_v=calculated_minimum,
        calculated_output_maximum_v=calculated_maximum,
        pin_nets=observed_pin_nets,
        basis=requirement.basis,
        issues=tuple(issues),
    )


def scan_regulator_feedback_map(
    specification: RegulatorFeedbackMap,
    observed: NetlistContract,
    netlist_sha256: str,
) -> RegulatorFeedbackCoverageReport:
    """Check authored conventional feedback dividers against one native netlist export."""
    pins_by_net = _pin_nets(observed)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    entries = tuple(
        _entry(requirement, observed, pins_by_net, dnp_references)
        for requirement in specification.regulators
    )
    status = "INCOMPLETE" if any(entry.status == "INCOMPLETE" for entry in entries) else "COMPLETE"
    return RegulatorFeedbackCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
