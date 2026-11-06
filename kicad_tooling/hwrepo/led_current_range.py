"""Compare authored LED current windows with exact native netlist paths."""

from __future__ import annotations

import hashlib
import json
import math

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_source_identity import component_identity_issues
from .led_current_models import (
    LedCurrentMap,
    LedCurrentRangeEntry,
    LedCurrentRequirement,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_inventory_contains, netlist_pin_net_index
from .resistor_paths import direct_resistors, resistance_ohms


def led_current_map_sha256(led_map: LedCurrentMap) -> str:
    """Hash authored LED requirements independent of their list order."""
    payload = led_map.model_dump(mode="json", exclude_none=True)
    payload["leds"] = sorted(payload["leds"], key=lambda item: (item["id"].casefold(), item["id"]))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_led_current_requirement(
    requirement: LedCurrentRequirement,
    observed: NetlistContract,
    *,
    map_sha256: str,
    netlist_sha256: str | None,
    map_basis: str,
) -> LedCurrentRangeEntry:
    """Compare one mapped LED and resistor with its authored DC current envelope."""
    issues: list[str] = []
    incomplete = False
    if netlist_sha256 is None:
        issues.append("Source-bound native netlist SHA-256 is unavailable")
        incomplete = True
    component_requirements = (
        (
            requirement.led_reference,
            requirement.expected_led_value,
            requirement.expected_led_symbol,
            requirement.expected_led_footprint,
        ),
        (
            requirement.resistor.reference,
            None,
            requirement.resistor.expected_symbol,
            requirement.resistor.expected_footprint,
        ),
    )
    for reference, value, symbol, footprint in component_requirements:
        identity_issues = component_identity_issues(
            observed,
            reference,
            value,
            symbol,
            footprint,
        )
        if identity_issues:
            issues.extend(identity_issues)
            incomplete = True

    mapped_pins = (
        requirement.anode_pin,
        requirement.cathode_pin,
        requirement.resistor.outer_pin,
        requirement.resistor.led_side_pin,
    )
    pin_index = netlist_pin_net_index(observed)
    observed_pin_nets: dict[str, tuple[str, ...]] = {}
    pin_evidence = {
        pin.casefold()
        for pin in (
            *observed.pin_functions,
            *observed.pin_electrical_types,
            *(item for net_pins in observed.nets.values() for item in net_pins),
        )
    }
    for pin in mapped_pins:
        inventory = netlist_pin_inventory_contains(observed, pin)
        if inventory is None:
            issues.append(f"{pin} has no native component-pin inventory")
            incomplete = True
        elif not inventory:
            issues.append(f"{pin} is absent from the native component-pin inventory")
            incomplete = True
        if pin.casefold() not in pin_evidence:
            issues.append(f"{pin} has no native pin evidence")
            incomplete = True
        observed_pin_nets[pin] = tuple(sorted(pin_index.get(pin.casefold(), ())))

    expected_pin_functions = (
        (requirement.anode_pin, requirement.expected_anode_function),
        (requirement.cathode_pin, requirement.expected_cathode_function),
    )
    for pin, expected in expected_pin_functions:
        actual = lookup_unique_casefold(observed.pin_functions, pin)
        if actual is None:
            issues.append(f"{pin} has no unambiguous native pin function")
            incomplete = True
        elif actual.strip().casefold() != expected.strip().casefold():
            issues.append(f"{pin} function is {actual}; expected {expected}")
            incomplete = True

    for pin in mapped_pins:
        actual_type = lookup_unique_casefold(observed.pin_electrical_types, pin)
        if actual_type is None:
            issues.append(f"{pin} has no unambiguous native electrical type")
            incomplete = True
        elif actual_type.casefold() != "passive":
            issues.append(f"{pin} electrical type is {actual_type}; expected passive")
            incomplete = True

    expected_pin_numbers = {
        reference: {pin.rsplit(".", maxsplit=1)[-1].casefold() for pin in pins}
        for reference, pins in (
            (requirement.led_reference, (requirement.anode_pin, requirement.cathode_pin)),
            (
                requirement.resistor.reference,
                (requirement.resistor.outer_pin, requirement.resistor.led_side_pin),
            ),
        )
    }
    for reference, expected_numbers in expected_pin_numbers.items():
        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None:
            issues.append(f"{reference} has no complete native pin-number inventory")
            incomplete = True
        elif {str(number).casefold() for number in inventory} != expected_numbers:
            issues.append(
                f"{reference} native pin inventory differs from the mapped two-terminal part"
            )
            incomplete = True

    dnp = {reference.casefold() for reference in observed.dnp_components}
    for reference in (requirement.led_reference, requirement.resistor.reference):
        if reference.casefold() in dnp:
            issues.append(f"Mapped LED-current component {reference} is not fitted")
            incomplete = True

    if requirement.resistor_leg == "anode":
        expected_nets = (
            (requirement.resistor.outer_pin, requirement.source_net, "resistor source"),
            (requirement.resistor.led_side_pin, requirement.led_side_net, "resistor LED side"),
            (requirement.anode_pin, requirement.led_side_net, "LED anode"),
            (requirement.cathode_pin, requirement.return_net, "LED cathode"),
        )
    else:
        expected_nets = (
            (requirement.anode_pin, requirement.source_net, "LED anode"),
            (requirement.cathode_pin, requirement.led_side_net, "LED cathode"),
            (requirement.resistor.led_side_pin, requirement.led_side_net, "resistor LED side"),
            (requirement.resistor.outer_pin, requirement.return_net, "resistor return"),
        )
    for pin, expected_net, role in expected_nets:
        actual = observed_pin_nets[pin]
        if actual != (expected_net,):
            issues.append(
                f"{role} pin {pin} is on {', '.join(actual) or 'unconnected'}; "
                f"expected {expected_net}"
            )
            incomplete = True

    mapped_resistor = requirement.resistor.reference.casefold()
    tracked_nets = {
        requirement.source_net.casefold(),
        requirement.led_side_net.casefold(),
        requirement.return_net.casefold(),
    }
    extra_resistors = tuple(
        item.reference
        for item in direct_resistors(
            observed,
            include_zero_ohm=True,
            include_device_r_symbol=True,
        )
        if item.reference.casefold() != mapped_resistor
        and (
            requirement.led_side_net.casefold()
            in {item.first_net.casefold(), item.second_net.casefold()}
            or {item.first_net.casefold(), item.second_net.casefold()} <= tracked_nets
        )
    )
    if extra_resistors:
        issues.append(
            "Unmapped fitted resistors touch the mapped LED path and can change its current: "
            + ", ".join(extra_resistors)
        )
        incomplete = True

    resistor_component = lookup_unique_casefold(observed.components, requirement.resistor.reference)
    measured = None if resistor_component is None else resistance_ohms(resistor_component.value)
    if measured is None or not math.isfinite(measured) or measured <= 0:
        issues.append(
            f"{requirement.resistor.reference} value "
            f"{getattr(resistor_component, 'value', '<missing>')} is not a supported positive "
            "nominal resistance"
        )
        incomplete = True
        measured = None

    out_of_range = False
    if measured is not None and not (
        requirement.resistor.minimum_nominal_resistance_ohms
        <= measured
        <= requirement.resistor.maximum_nominal_resistance_ohms
    ):
        issues.append(
            f"{requirement.resistor.reference} is {measured:g} Ω; authored nominal range is "
            f"{requirement.resistor.minimum_nominal_resistance_ohms:g}–"
            f"{requirement.resistor.maximum_nominal_resistance_ohms:g} Ω"
        )
        out_of_range = True

    current_minimum: float | None = None
    current_maximum: float | None = None
    if measured is not None and not incomplete:
        tolerance = requirement.resistor.maximum_tolerance_percent / 100
        resistance_minimum = measured * (1 - tolerance)
        resistance_maximum = measured * (1 + tolerance)
        try:
            current_minimum = max(
                0.0,
                (requirement.minimum_source_voltage_v - requirement.maximum_forward_voltage_v)
                / resistance_maximum
                * 1000,
            )
            current_maximum = max(
                0.0,
                (requirement.maximum_source_voltage_v - requirement.minimum_forward_voltage_v)
                / resistance_minimum
                * 1000,
            )
        except (OverflowError, ZeroDivisionError):
            issues.append("Calculated LED current envelope is not finite")
            incomplete = True
        else:
            if not (math.isfinite(current_minimum) and math.isfinite(current_maximum)):
                issues.append("Calculated LED current envelope is not finite")
                incomplete = True
                current_minimum = None
                current_maximum = None
            elif (
                current_minimum < requirement.minimum_target_current_ma
                or current_maximum > requirement.maximum_target_current_ma
            ):
                issues.append(
                    f"Calculated LED current envelope {current_minimum:g}–{current_maximum:g} mA "
                    "is outside the authored target "
                    f"{requirement.minimum_target_current_ma:g}–"
                    f"{requirement.maximum_target_current_ma:g} mA"
                )
                out_of_range = True

    status = "INCOMPLETE" if incomplete else "OUT_OF_RANGE" if out_of_range else "MATCHED"
    return LedCurrentRangeEntry(
        id=requirement.id,
        status=status,
        led_reference=requirement.led_reference,
        resistor_reference=requirement.resistor.reference,
        map_sha256=map_sha256,
        netlist_sha256=netlist_sha256,
        source_net=requirement.source_net,
        return_net=requirement.return_net,
        led_side_net=requirement.led_side_net,
        map_basis=map_basis,
        source_voltage_basis=requirement.source_voltage_basis,
        forward_voltage_basis=requirement.forward_voltage_basis,
        target_current_basis=requirement.target_current_basis,
        source_minimum_v=requirement.minimum_source_voltage_v,
        source_maximum_v=requirement.maximum_source_voltage_v,
        forward_voltage_minimum_v=requirement.minimum_forward_voltage_v,
        forward_voltage_maximum_v=requirement.maximum_forward_voltage_v,
        target_current_minimum_ma=requirement.minimum_target_current_ma,
        target_current_maximum_ma=requirement.maximum_target_current_ma,
        minimum_nominal_resistance_ohms=requirement.resistor.minimum_nominal_resistance_ohms,
        maximum_nominal_resistance_ohms=requirement.resistor.maximum_nominal_resistance_ohms,
        maximum_tolerance_percent=requirement.resistor.maximum_tolerance_percent,
        tolerance_basis=requirement.resistor.tolerance_basis,
        resistance_ohms=measured,
        calculated_current_minimum_ma=current_minimum,
        calculated_current_maximum_ma=current_maximum,
        pin_nets=observed_pin_nets,
        issues=tuple(issues),
    )


def scan_led_current_map(
    led_map: LedCurrentMap,
    observed: NetlistContract,
    netlist_sha256: str | None,
) -> tuple[LedCurrentRangeEntry, ...]:
    """Evaluate map entries in stable order against one native netlist digest."""
    map_sha256 = led_current_map_sha256(led_map)
    return tuple(
        evaluate_led_current_requirement(
            item,
            observed,
            map_sha256=map_sha256,
            netlist_sha256=netlist_sha256,
            map_basis=led_map.basis,
        )
        for item in sorted(led_map.leds, key=lambda item: (item.id.casefold(), item.id))
    )
