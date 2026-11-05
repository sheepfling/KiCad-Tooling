"""Source-bound checks for explicitly mapped single-ended signal dividers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_source_identity import component_identity_issues
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_inventory_contains, netlist_pin_net_index
from .resistor_paths import direct_resistors, resistance_ohms
from .signal_divider_models import (
    SignalDividerCoverageEntry,
    SignalDividerCoverageReport,
    SignalDividerMap,
    SignalDividerRequirement,
)
from .voltage_divider_math import divider_tap_fraction


def evaluate_signal_divider_requirement(
    requirement: SignalDividerRequirement,
    observed: NetlistContract,
    pins_by_net: Mapping[str, AbstractSet[str]],
    dnp_references: AbstractSet[str],
) -> SignalDividerCoverageEntry:
    issues: list[str] = []
    component_requirements = (
        (
            requirement.receiver_reference,
            requirement.expected_receiver_value,
            requirement.expected_receiver_symbol,
            requirement.expected_receiver_footprint,
        ),
        *(
            (item.reference, None, item.expected_symbol, item.expected_footprint)
            for item in (requirement.upper_resistor, requirement.lower_resistor)
        ),
    )
    identity_valid = True
    for reference, expected_value, symbol, footprint in component_requirements:
        identity_issues = component_identity_issues(
            observed, reference, expected_value, symbol, footprint
        )
        issues.extend(identity_issues)
        identity_valid = not identity_issues and identity_valid

    references = (
        requirement.receiver_reference,
        requirement.upper_resistor.reference,
        requirement.lower_resistor.reference,
    )
    dnp = tuple(reference for reference in references if reference.casefold() in dnp_references)
    if dnp:
        issues.append("Mapped signal-divider components are not fitted: " + ", ".join(dnp))
        identity_valid = False

    mapped_pins = (
        requirement.receiver_pin,
        requirement.upper_resistor.outer_pin,
        requirement.upper_resistor.divider_pin,
        requirement.lower_resistor.divider_pin,
        requirement.lower_resistor.outer_pin,
    )
    pin_evidence = {
        pin.casefold()
        for pin in (
            *observed.pin_functions,
            *observed.pin_electrical_types,
            *(item for net_pins in observed.nets.values() for item in net_pins),
        )
    }
    observed_pin_nets: dict[str, tuple[str, ...]] = {}
    pins_valid = True
    for pin in mapped_pins:
        inventory = netlist_pin_inventory_contains(observed, pin)
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

    receiver_function = lookup_unique_casefold(observed.pin_functions, requirement.receiver_pin)
    if receiver_function is None:
        issues.append(f"{requirement.receiver_pin} has no native symbol pin function")
        pins_valid = False
    elif (
        receiver_function.strip().casefold()
        != requirement.expected_receiver_pin_function.strip().casefold()
    ):
        issues.append(
            f"{requirement.receiver_pin} function is {receiver_function}; expected "
            f"{requirement.expected_receiver_pin_function}"
        )
        pins_valid = False
    receiver_electrical_type = lookup_unique_casefold(
        observed.pin_electrical_types, requirement.receiver_pin
    )
    if receiver_electrical_type is None:
        issues.append(f"{requirement.receiver_pin} has no native electrical type")
        pins_valid = False
    elif receiver_electrical_type.casefold() != requirement.expected_receiver_electrical_type:
        issues.append(
            f"{requirement.receiver_pin} electrical type is {receiver_electrical_type}; expected "
            f"{requirement.expected_receiver_electrical_type}"
        )
        pins_valid = False

    expected_nets = (
        (requirement.receiver_pin, requirement.input_net, "receiver input"),
        (requirement.upper_resistor.outer_pin, requirement.source_net, "upper-resistor source"),
        (requirement.upper_resistor.divider_pin, requirement.input_net, "upper-resistor tap"),
        (requirement.lower_resistor.divider_pin, requirement.input_net, "lower-resistor tap"),
        (
            requirement.lower_resistor.outer_pin,
            requirement.reference_net,
            "lower-resistor reference",
        ),
    )
    nets_valid = True
    for pin, expected_net, role in expected_nets:
        actual = observed_pin_nets[pin]
        if actual != (expected_net,):
            issues.append(
                f"{role} pin {pin} is on {', '.join(actual) or 'unconnected'}; "
                f"expected {expected_net}"
            )
            nets_valid = False

    mapped_resistors = {
        requirement.upper_resistor.reference.casefold(),
        requirement.lower_resistor.reference.casefold(),
    }
    extra_input_resistors = tuple(
        item.reference
        for item in direct_resistors(observed, include_zero_ohm=True, include_device_r_symbol=True)
        if item.reference.casefold() not in mapped_resistors
        and requirement.input_net.casefold()
        in (item.first_net.casefold(), item.second_net.casefold())
    )
    if extra_input_resistors:
        issues.append(
            "Unmapped fitted resistors touch the divider input net and may load its nominal "
            "voltage: " + ", ".join(extra_input_resistors)
        )
        nets_valid = False

    nominal_values: dict[str, float] = {}
    values_valid = True
    value_out_of_range = False
    for resistor in (requirement.upper_resistor, requirement.lower_resistor):
        component = lookup_unique_casefold(observed.components, resistor.reference)
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
            value_out_of_range = True

    calculated_minimum: float | None = None
    calculated_maximum: float | None = None
    calculation_valid = True
    if identity_valid and pins_valid and nets_valid and values_valid and len(nominal_values) == 2:
        try:
            fraction = divider_tap_fraction(
                nominal_values[requirement.upper_resistor.reference],
                nominal_values[requirement.lower_resistor.reference],
            )
            calculated_minimum = requirement.minimum_source_voltage_v * fraction
            calculated_maximum = requirement.maximum_source_voltage_v * fraction
        except (OverflowError, ValueError):
            calculation_valid = False
        else:
            if not (math.isfinite(calculated_minimum) and math.isfinite(calculated_maximum)):
                calculation_valid = False
            elif (
                calculated_minimum < requirement.minimum_input_voltage_v
                or calculated_maximum > requirement.maximum_input_voltage_v
            ):
                issues.append(
                    f"Calculated nominal input range {calculated_minimum:g}–"
                    f"{calculated_maximum:g} V is outside authored target "
                    f"{requirement.minimum_input_voltage_v:g}–"
                    f"{requirement.maximum_input_voltage_v:g} V"
                )
        if not calculation_valid:
            issues.append("Calculated divider output exceeds the supported finite numeric range")

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

    return SignalDividerCoverageEntry(
        id=requirement.id,
        receiver_reference=requirement.receiver_reference,
        status=status,
        source_net=requirement.source_net,
        input_net=requirement.input_net,
        reference_net=requirement.reference_net,
        nominal_resistance_ohms=nominal_values,
        calculated_input_minimum_v=calculated_minimum,
        calculated_input_maximum_v=calculated_maximum,
        source_minimum_v=requirement.minimum_source_voltage_v,
        source_maximum_v=requirement.maximum_source_voltage_v,
        target_input_minimum_v=requirement.minimum_input_voltage_v,
        target_input_maximum_v=requirement.maximum_input_voltage_v,
        pin_nets=observed_pin_nets,
        basis=requirement.basis,
        issues=tuple(issues),
    )


def scan_signal_divider_map(
    specification: SignalDividerMap,
    observed: NetlistContract,
    netlist_sha256: str,
) -> SignalDividerCoverageReport:
    """Compare only explicitly authored signal dividers with native netlist evidence."""
    pins_by_net = netlist_pin_net_index(observed)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    entries = tuple(
        evaluate_signal_divider_requirement(requirement, observed, pins_by_net, dnp_references)
        for requirement in specification.dividers
    )
    status = "INCOMPLETE" if any(entry.status == "INCOMPLETE" for entry in entries) else "COMPLETE"
    return SignalDividerCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
