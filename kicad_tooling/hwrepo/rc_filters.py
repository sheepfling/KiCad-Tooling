"""Deterministic checks for explicitly mapped first-order RC low-pass filters."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal, DecimalException, localcontext
from typing import TypeVar

from .crystal_networks import parse_capacitance_pf
from .models import (
    ComponentContract,
    NetlistContract,
    RcFilterCoverageEntry,
    RcFilterCoverageReport,
    RcFilterMap,
    RcFilterRequirement,
)
from .resistor_paths import (
    direct_resistors,
    resistance_ohms,
)

_Value = TypeVar("_Value")
_TAU = Decimal("6.2831853071795864769252867665590057683943387987502")
_CAPACITOR_REFERENCE = re.compile(r"^C[A-Z]*[0-9]+$", re.IGNORECASE)


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


def _component_issues(
    observed: NetlistContract,
    reference: str,
    expected_symbol: str,
    expected_footprint: str,
    expected_pins: tuple[str, str],
    dnp: set[str],
) -> list[str]:
    issues: list[str] = []
    component: ComponentContract | None = _lookup(observed.components, reference)
    if component is None:
        issues.append(f"Mapped component {reference} is missing or ambiguous in the native netlist")
        return issues
    symbol = _lookup(observed.component_symbols, reference)
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )
    if reference.casefold() in dnp:
        issues.append(f"{reference} is marked DNP but the mapped filter requires it fitted")
    inventory = _lookup(observed.component_pin_numbers, reference)
    if inventory is None:
        issues.append(f"{reference} native symbol pin inventory is unavailable")
    else:
        expected = {pin.rsplit(".", 1)[1].casefold() for pin in expected_pins}
        actual = {str(number).casefold() for number in inventory}
        if actual != expected:
            missing = sorted(expected - actual)
            unlisted = sorted(actual - expected)
            if missing:
                issues.append(
                    f"{reference} mapped pins are missing from native inventory: {missing}"
                )
            if unlisted:
                issues.append(f"{reference} has unmapped native pins: {unlisted}")
    return issues


def _unlisted_parallel_components(
    requirement: RcFilterRequirement,
    observed: NetlistContract,
) -> tuple[str, ...]:
    mapped = {requirement.resistor_reference.casefold(), requirement.capacitor_reference.casefold()}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    relevant_pairs = {
        frozenset((requirement.input_net.casefold(), requirement.filtered_net.casefold())),
        frozenset((requirement.filtered_net.casefold(), requirement.reference_net.casefold())),
        frozenset((requirement.input_net.casefold(), requirement.reference_net.casefold())),
    }
    extras: set[str] = set()
    for resistor in direct_resistors(observed):
        if resistor.reference.casefold() in mapped:
            continue
        if (
            frozenset((resistor.first_net.casefold(), resistor.second_net.casefold()))
            in relevant_pairs
        ):
            extras.add(resistor.reference)

    for reference, component in observed.components.items():
        if (
            reference.casefold() in mapped
            or reference.casefold() in dnp
            or _CAPACITOR_REFERENCE.fullmatch(reference) is None
            or parse_capacitance_pf(component.value) is None
        ):
            continue
        inventory = _lookup(observed.component_pin_numbers, reference)
        if inventory is None or len(inventory) != 2:
            continue
        assignments = tuple(_pin_nets(observed, f"{reference}.{number}") for number in inventory)
        if any(len(nets) != 1 for nets in assignments):
            continue
        pair = frozenset(nets[0].casefold() for nets in assignments)
        if pair in relevant_pairs:
            extras.add(reference)
    return tuple(sorted(extras, key=str.casefold))


def _entry(requirement: RcFilterRequirement, observed: NetlistContract) -> RcFilterCoverageEntry:
    structural_issues: list[str] = []
    range_issues: list[str] = []
    dnp = {reference.casefold() for reference in observed.dnp_components}
    structural_issues.extend(
        _component_issues(
            observed,
            requirement.resistor_reference,
            requirement.expected_resistor_symbol,
            requirement.expected_resistor_footprint,
            (requirement.resistor_first_pin, requirement.resistor_second_pin),
            dnp,
        )
    )
    structural_issues.extend(
        _component_issues(
            observed,
            requirement.capacitor_reference,
            requirement.expected_capacitor_symbol,
            requirement.expected_capacitor_footprint,
            (requirement.capacitor_signal_pin, requirement.capacitor_reference_pin),
            dnp,
        )
    )

    mapped_pins = (
        requirement.resistor_first_pin,
        requirement.resistor_second_pin,
        requirement.capacitor_signal_pin,
        requirement.capacitor_reference_pin,
    )
    pin_nets = {pin: _pin_nets(observed, pin) for pin in mapped_pins}
    for pin, nets in pin_nets.items():
        if len(nets) != 1:
            structural_issues.append(
                f"{pin} is {'unconnected' if not nets else 'assigned to multiple nets'}"
            )
    if all(len(nets) == 1 for nets in pin_nets.values()):
        resistor_nets = {
            pin_nets[requirement.resistor_first_pin][0].casefold(),
            pin_nets[requirement.resistor_second_pin][0].casefold(),
        }
        expected_resistor_nets = {
            requirement.input_net.casefold(),
            requirement.filtered_net.casefold(),
        }
        capacitor_nets = {
            pin_nets[requirement.capacitor_signal_pin][0].casefold(),
            pin_nets[requirement.capacitor_reference_pin][0].casefold(),
        }
        expected_capacitor_nets = {
            requirement.filtered_net.casefold(),
            requirement.reference_net.casefold(),
        }
        if resistor_nets != expected_resistor_nets:
            structural_issues.append(
                f"{requirement.resistor_reference} spans {sorted(resistor_nets)}; "
                f"expected {sorted(expected_resistor_nets)}"
            )
        if capacitor_nets != expected_capacitor_nets:
            structural_issues.append(
                f"{requirement.capacitor_reference} spans {sorted(capacitor_nets)}; "
                f"expected {sorted(expected_capacitor_nets)}"
            )

    extras = _unlisted_parallel_components(requirement, observed)
    if extras:
        structural_issues.append(
            "Unlisted fitted direct passive components touch the mapped filter nodes: "
            + ", ".join(extras)
        )

    resistor: ComponentContract | None = _lookup(
        observed.components, requirement.resistor_reference
    )
    capacitor: ComponentContract | None = _lookup(
        observed.components, requirement.capacitor_reference
    )
    resistance = None if resistor is None else resistance_ohms(resistor.value)
    capacitance = None if capacitor is None else parse_capacitance_pf(capacitor.value)
    if resistance is None or not math.isfinite(resistance) or resistance <= 0:
        structural_issues.append(
            f"{requirement.resistor_reference} value is not a supported positive resistance"
        )
        resistance = None
    if capacitance is None or not capacitance.is_finite() or capacitance <= 0:
        structural_issues.append(
            f"{requirement.capacitor_reference} value is not a supported positive capacitance"
        )
        capacitance = None

    calculated_corner: float | None = None
    if resistance is not None and capacitance is not None and not structural_issues:
        try:
            with localcontext() as context:
                context.prec = 50
                corner = Decimal(1) / (
                    _TAU * Decimal(str(resistance)) * capacitance * Decimal("1e-12")
                )
            as_float = float(corner)
            if math.isfinite(as_float) and as_float > 0:
                calculated_corner = as_float
            else:
                structural_issues.append(
                    "Calculated RC corner frequency is not finite and positive"
                )
        except (DecimalException, OverflowError, ValueError):
            structural_issues.append("Could not calculate the mapped RC corner frequency")

    if resistance is not None and not (
        requirement.minimum_nominal_resistance_ohms
        <= resistance
        <= requirement.maximum_nominal_resistance_ohms
    ):
        range_issues.append(
            f"{requirement.resistor_reference} nominal value is {resistance:g} Ω; reviewed range is "
            f"{requirement.minimum_nominal_resistance_ohms:g}–"
            f"{requirement.maximum_nominal_resistance_ohms:g} Ω"
        )
    if capacitance is not None and not (
        Decimal(str(requirement.minimum_nominal_capacitance_pf))
        <= capacitance
        <= Decimal(str(requirement.maximum_nominal_capacitance_pf))
    ):
        range_issues.append(
            f"{requirement.capacitor_reference} nominal value is {capacitance:g} pF; "
            f"reviewed range is {requirement.minimum_nominal_capacitance_pf:g}–"
            f"{requirement.maximum_nominal_capacitance_pf:g} pF"
        )
    if calculated_corner is not None and not (
        requirement.minimum_target_corner_hz
        <= calculated_corner
        <= requirement.maximum_target_corner_hz
    ):
        range_issues.append(
            f"Calculated nominal corner is {calculated_corner:g} Hz; target is "
            f"{requirement.minimum_target_corner_hz:g}–"
            f"{requirement.maximum_target_corner_hz:g} Hz"
        )

    status = "INCOMPLETE" if structural_issues else "OUT_OF_RANGE" if range_issues else "COMPLETE"
    return RcFilterCoverageEntry(
        id=requirement.id,
        resistor_reference=requirement.resistor_reference,
        capacitor_reference=requirement.capacitor_reference,
        status=status,
        input_net=requirement.input_net,
        filtered_net=requirement.filtered_net,
        reference_net=requirement.reference_net,
        resistance_ohms=resistance,
        capacitance_pf=None if capacitance is None else float(capacitance),
        calculated_corner_hz=calculated_corner,
        target_minimum_corner_hz=requirement.minimum_target_corner_hz,
        target_maximum_corner_hz=requirement.maximum_target_corner_hz,
        nominal_resistance_range_ohms=(
            requirement.minimum_nominal_resistance_ohms,
            requirement.maximum_nominal_resistance_ohms,
        ),
        nominal_capacitance_range_pf=(
            requirement.minimum_nominal_capacitance_pf,
            requirement.maximum_nominal_capacitance_pf,
        ),
        pin_nets=pin_nets,
        unlisted_parallel_components=extras,
        basis=requirement.basis,
        issues=(*structural_issues, *range_issues),
    )


def scan_rc_filter_map(
    requirement_map: RcFilterMap,
    observed: NetlistContract,
    netlist_sha256: str,
) -> RcFilterCoverageReport:
    """Compare authored first-order RC filters with source-bound netlist evidence."""
    entries = tuple(_entry(requirement, observed) for requirement in requirement_map.filters)
    return RcFilterCoverageReport(
        status="INCOMPLETE" if any(item.status == "INCOMPLETE" for item in entries) else "COMPLETE",
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
