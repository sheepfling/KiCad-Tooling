"""Deterministic checks for explicitly mapped Pierce crystal load networks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, DecimalException, InvalidOperation, localcontext
from typing import TypeVar

from .models import (
    CrystalNetworkCoverageEntry,
    CrystalNetworkCoverageReport,
    CrystalNetworkMap,
    CrystalNetworkRequirement,
    NetlistContract,
)

_CAPACITANCE_VALUE = re.compile(
    r"^\s*(?P<number>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))\s*"
    r"(?P<unit>pf|nf|uf|μf|µf|p|n|u)\s*$",
    re.IGNORECASE,
)
_PICO_FARADS_PER_UNIT = {
    "p": Decimal(1),
    "pf": Decimal(1),
    "n": Decimal(1000),
    "nf": Decimal(1000),
    "u": Decimal(1000000),
    "uf": Decimal(1000000),
    "μf": Decimal(1000000),
    "µf": Decimal(1000000),
}
_Value = TypeVar("_Value")


def parse_capacitance_pf(value: str) -> Decimal | None:
    """Parse an intentionally small set of explicit KiCad capacitance spellings."""
    if len(value) > 128:
        return None
    match = _CAPACITANCE_VALUE.fullmatch(value)
    if match is None:
        return None
    try:
        number = Decimal(match.group("number"))
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    unit = match.group("unit").casefold()
    try:
        with localcontext() as context:
            context.prec = 50
            return number * _PICO_FARADS_PER_UNIT[unit]
    except DecimalException:
        return None


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


def _component_pin_is_in_inventory(observed: NetlistContract, pin: str) -> bool | None:
    reference, separator, number = pin.rpartition(".")
    if not separator:
        return False
    inventory = _lookup(observed.component_pin_numbers, reference)
    if inventory is None:
        return None
    return any(str(candidate).casefold() == number.casefold() for candidate in inventory)


def _check_identity(
    observed: NetlistContract,
    reference: str,
    expected_value: str | None,
    expected_symbol: str,
    expected_footprint: str,
    issues: list[str],
) -> None:
    component = _lookup(observed.components, reference)
    symbol = _lookup(observed.component_symbols, reference)
    if component is None:
        issues.append(f"Mapped component {reference} is missing or ambiguous in the native netlist")
        return
    if expected_value is not None and component.value != expected_value:
        issues.append(f"{reference} value is {component.value}; expected {expected_value}")
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )


def _entry(
    requirement: CrystalNetworkRequirement,
    observed: NetlistContract,
) -> CrystalNetworkCoverageEntry:
    issues: list[str] = []
    components = (
        (
            requirement.oscillator_reference,
            requirement.expected_oscillator_value,
            requirement.expected_oscillator_symbol,
            requirement.expected_oscillator_footprint,
        ),
        (
            requirement.resonator_reference,
            requirement.expected_resonator_value,
            requirement.expected_resonator_symbol,
            requirement.expected_resonator_footprint,
        ),
        *(
            (cap.reference, None, cap.expected_symbol, cap.expected_footprint)
            for cap in requirement.load_capacitors
        ),
    )
    for reference, value, symbol, footprint in components:
        _check_identity(observed, reference, value, symbol, footprint, issues)

    fitted = {reference.casefold() for reference in observed.dnp_components}
    not_fitted = sorted(reference for reference, *_ in components if reference.casefold() in fitted)
    if not_fitted:
        issues.append(f"Mapped crystal network components are marked DNP: {', '.join(not_fitted)}")

    pins = (
        requirement.oscillator_input_pin,
        requirement.oscillator_output_pin,
        requirement.resonator_input_pin,
        requirement.resonator_output_pin,
        *(
            pin
            for cap in requirement.load_capacitors
            for pin in (cap.signal_pin, cap.reference_pin)
        ),
    )
    node_nets = {pin: _pin_nets(observed, pin) for pin in pins}
    extra_capacitors: tuple[str, ...] = ()
    extra_capacitor_pin_nets: dict[str, tuple[str, ...]] = {}
    for pin in pins:
        in_inventory = _component_pin_is_in_inventory(observed, pin)
        if in_inventory is None:
            issues.append(f"Native pin inventory is unavailable for {pin}")
        elif not in_inventory:
            issues.append(f"Mapped pin {pin} is absent from the native component pin inventory")
        if len(node_nets[pin]) != 1:
            assignment = "unconnected" if not node_nets[pin] else "assigned to multiple nets"
            issues.append(f"Mapped pin {pin} is {assignment}")

    if all(len(node_nets[pin]) == 1 for pin in pins):
        input_net = node_nets[requirement.oscillator_input_pin][0]
        output_net = node_nets[requirement.oscillator_output_pin][0]
        resonator_input_net = node_nets[requirement.resonator_input_pin][0]
        resonator_output_net = node_nets[requirement.resonator_output_pin][0]
        capacitor_signal_nets = [
            node_nets[cap.signal_pin][0] for cap in requirement.load_capacitors
        ]
        capacitor_reference_nets = [
            node_nets[cap.reference_pin][0] for cap in requirement.load_capacitors
        ]
        if input_net.casefold() == output_net.casefold():
            issues.append("Mapped oscillator input and output pins share one net")
        if resonator_input_net.casefold() != input_net.casefold():
            issues.append(
                f"Resonator pin {requirement.resonator_input_pin} does not connect to "
                f"oscillator input {requirement.oscillator_input_pin}"
            )
        if resonator_output_net.casefold() != output_net.casefold():
            issues.append(
                f"Resonator pin {requirement.resonator_output_pin} does not connect to "
                f"oscillator output {requirement.oscillator_output_pin}"
            )
        if {net.casefold() for net in capacitor_signal_nets} != {
            input_net.casefold(),
            output_net.casefold(),
        }:
            issues.append(
                "The two load-capacitor signal pins do not span oscillator input and output"
            )
        if any(
            net.casefold() != requirement.reference_net.casefold()
            for net in capacitor_reference_nets
        ):
            issues.append(
                f"Load-capacitor reference pins do not both connect to {requirement.reference_net}"
            )
        if requirement.reference_net.casefold() in {input_net.casefold(), output_net.casefold()}:
            issues.append(
                "The declared reference net is also assigned to an oscillator signal node"
            )
        mapped_references = {reference.casefold() for reference, *_ in components}
        dnp_references = {reference.casefold() for reference in observed.dnp_components}
        unlisted: list[str] = []
        for reference, component in observed.components.items():
            if reference.casefold() in mapped_references or reference.casefold() in dnp_references:
                continue
            if parse_capacitance_pf(component.value) is None:
                continue
            inventory = _lookup(observed.component_pin_numbers, reference)
            if inventory is None or len(inventory) != 2:
                continue
            assigned = tuple(_pin_nets(observed, f"{reference}.{number}") for number in inventory)
            if any(len(nets) != 1 for nets in assigned):
                continue
            normalized = {nets[0].casefold() for nets in assigned}
            signal_nodes = {input_net.casefold(), output_net.casefold()}
            if (
                requirement.reference_net.casefold() in normalized
                and len(normalized) == 2
                and len(normalized & signal_nodes) == 1
            ):
                unlisted.append(reference)
                extra_capacitor_pin_nets[reference] = tuple(
                    f"{reference}.{number} -> {nets[0]}"
                    for number, nets in zip(inventory, assigned, strict=True)
                )
        extra_capacitors = tuple(sorted(unlisted, key=str.casefold))
        for reference in extra_capacitors:
            issues.append(
                f"Potential unlisted load capacitor {reference} connects an oscillator signal "
                "node to the reference net"
            )

    capacitance_values: dict[str, Decimal] = {}
    for cap in requirement.load_capacitors:
        component = _lookup(observed.components, cap.reference)
        if component is None:
            continue
        capacitance = parse_capacitance_pf(component.value)
        if capacitance is None:
            issues.append(
                f"{cap.reference} value {component.value!r} is not a supported explicit "
                "capacitance spelling"
            )
            continue
        capacitance_values[cap.reference] = capacitance
        minimum = Decimal(str(cap.minimum_nominal_capacitance_pf))
        maximum = Decimal(str(cap.maximum_nominal_capacitance_pf))
        if not minimum <= capacitance <= maximum:
            issues.append(
                f"{cap.reference} nominal value is {capacitance} pF; reviewed range is "
                f"{minimum}–{maximum} pF"
            )

    calculated_minimum: Decimal | None = None
    calculated_maximum: Decimal | None = None
    if len(capacitance_values) == 2:
        values = tuple(capacitance_values.values())
        try:
            with localcontext() as context:
                context.prec = 50
                series_load = values[0] * values[1] / (values[0] + values[1])
                calculated_minimum = series_load + Decimal(
                    str(requirement.minimum_stray_capacitance_pf)
                )
                calculated_maximum = series_load + Decimal(
                    str(requirement.maximum_stray_capacitance_pf)
                )
        except DecimalException:
            issues.append("Could not calculate the mapped crystal network nominal load range")

    if issues:
        status = "INCOMPLETE"
    elif calculated_minimum is None or calculated_maximum is None:
        status = "INCOMPLETE"
        issues.append(
            "Both mapped load-capacitor nominal values are required for the load estimate"
        )
    elif calculated_minimum < Decimal(
        str(requirement.minimum_target_load_pf)
    ) or calculated_maximum > Decimal(str(requirement.maximum_target_load_pf)):
        status = "OUT_OF_RANGE"
        issues.append(
            f"Calculated nominal load range {calculated_minimum}–{calculated_maximum} pF is "
            f"outside the reviewed target {requirement.minimum_target_load_pf}–"
            f"{requirement.maximum_target_load_pf} pF"
        )
    else:
        status = "COMPLETE"

    return CrystalNetworkCoverageEntry(
        oscillator_reference=requirement.oscillator_reference,
        resonator_reference=requirement.resonator_reference,
        load_capacitor_references=tuple(cap.reference for cap in requirement.load_capacitors),
        extra_capacitor_references=extra_capacitors,
        extra_capacitor_pin_nets=extra_capacitor_pin_nets,
        status=status,
        node_nets=node_nets,
        capacitance_pf={reference: float(value) for reference, value in capacitance_values.items()},
        calculated_minimum_load_pf=(
            None if calculated_minimum is None else float(calculated_minimum)
        ),
        calculated_maximum_load_pf=(
            None if calculated_maximum is None else float(calculated_maximum)
        ),
        target_minimum_load_pf=requirement.minimum_target_load_pf,
        target_maximum_load_pf=requirement.maximum_target_load_pf,
        minimum_stray_capacitance_pf=requirement.minimum_stray_capacitance_pf,
        maximum_stray_capacitance_pf=requirement.maximum_stray_capacitance_pf,
        basis=requirement.basis,
        issues=tuple(issues),
    )


def scan_crystal_network_map(
    requirement_map: CrystalNetworkMap,
    observed: NetlistContract,
    netlist_sha256: str,
) -> CrystalNetworkCoverageReport:
    """Compare every authored network with one exact native netlist export."""
    entries = tuple(_entry(requirement, observed) for requirement in requirement_map.networks)
    status = "INCOMPLETE" if any(entry.status == "INCOMPLETE" for entry in entries) else "COMPLETE"
    return CrystalNetworkCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
