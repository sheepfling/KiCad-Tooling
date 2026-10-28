"""Compare authored oscillator output topology with a native netlist."""

from __future__ import annotations

from dataclasses import dataclass

from .casefold_mapping_lookup import lookup_unique_casefold as _lookup
from .models import NetlistContract
from .oscillator_output_path_models import (
    OscillatorOutputPathMap,
    OscillatorOutputPathRequirement,
)
from .resistor_paths import direct_resistors, resistance_ohms


@dataclass(frozen=True, slots=True)
class OscillatorOutputPathMismatch:
    """One path whose native netlist differs from the authored requirement."""

    path_id: str
    basis: str
    oscillator_output_pin: str
    topology: str
    load_pins: tuple[str, ...]
    series_resistor: str | None
    issues: tuple[str, ...]


def _pin_nets(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                net
                for net, pins in observed.nets.items()
                if any(candidate.casefold() == pin.casefold() for candidate in pins)
            },
            key=str.casefold,
        )
    )


def _component_identity_issues(
    observed: NetlistContract,
    reference: str,
    *,
    expected_symbol: str,
    expected_footprint: str,
    expected_value: str | None,
    expected_part_id: str | None,
    expected_pins: tuple[str, ...],
    expected_pin_count: int | None,
    dnp: frozenset[str],
) -> list[str]:
    issues: list[str] = []
    component = _lookup(observed.components, reference)
    if component is None:
        issues.append(f"{reference} is absent or ambiguous in the native netlist")
    else:
        if component.footprint != expected_footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {expected_footprint}"
            )
        if expected_value is not None and component.value != expected_value:
            issues.append(f"{reference} value is {component.value}; expected {expected_value}")
        if expected_part_id is not None and (
            component.part_id is None or component.part_id.casefold() != expected_part_id.casefold()
        ):
            issues.append(
                f"{reference} PART_ID is {component.part_id or '<missing>'}; "
                f"expected {expected_part_id}"
            )
    if reference.casefold() in dnp:
        issues.append(f"{reference} is marked DNP but the mapped output path requires it fitted")
    symbol = _lookup(observed.component_symbols, reference)
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    inventory = _lookup(observed.component_pin_numbers, reference)
    if inventory is None:
        issues.append(f"{reference} native pin inventory is unavailable or ambiguous")
    else:
        numbers = {str(item).casefold() for item in inventory}
        for pin in expected_pins:
            number = pin.rsplit(".", 1)[1]
            if number.casefold() not in numbers:
                issues.append(f"{pin} is absent from the native pin inventory")
        if expected_pin_count is not None and len(inventory) != expected_pin_count:
            issues.append(
                f"{reference} has {len(inventory)} native pins; expected {expected_pin_count}"
            )
    return issues


def _path_issues(
    requirement: OscillatorOutputPathRequirement,
    observed: NetlistContract,
) -> tuple[str, ...]:
    dnp = frozenset(reference.casefold() for reference in observed.dnp_components)
    oscillator_reference = requirement.oscillator_reference
    issues = _component_identity_issues(
        observed,
        oscillator_reference,
        expected_symbol=requirement.expected_oscillator_symbol,
        expected_footprint=requirement.expected_oscillator_footprint,
        expected_value=requirement.expected_oscillator_value,
        expected_part_id=requirement.expected_oscillator_part_id,
        expected_pins=(requirement.output_pin,),
        expected_pin_count=None,
        dnp=dnp,
    )
    for load in sorted(requirement.load_pins, key=lambda item: item.pin.casefold()):
        issues.extend(
            _component_identity_issues(
                observed,
                load.reference,
                expected_symbol=load.expected_symbol,
                expected_footprint=load.expected_footprint,
                expected_value=load.expected_value,
                expected_part_id=load.expected_part_id,
                expected_pins=(load.pin,),
                expected_pin_count=None,
                dnp=dnp,
            )
        )

    path_pins = [requirement.output_pin, *(load.pin for load in requirement.load_pins)]
    resistor = requirement.series_resistor
    if resistor is not None:
        path_pins.extend((resistor.output_side_pin, resistor.load_side_pin))
        issues.extend(
            _component_identity_issues(
                observed,
                resistor.reference,
                expected_symbol=resistor.expected_symbol,
                expected_footprint=resistor.expected_footprint,
                expected_value=None,
                expected_part_id=resistor.expected_part_id,
                expected_pins=(resistor.output_side_pin, resistor.load_side_pin),
                expected_pin_count=2,
                dnp=dnp,
            )
        )
    pin_nets = {pin: _pin_nets(observed, pin) for pin in path_pins}
    for pin in sorted(path_pins, key=str.casefold):
        nets = pin_nets[pin]
        if len(nets) != 1:
            assignment = "unconnected" if not nets else f"assigned to multiple nets {nets}"
            issues.append(f"{pin} is {assignment}")

    if resistor is None:
        output_nets = pin_nets[requirement.output_pin]
        if len(output_nets) == 1:
            for load in sorted(requirement.load_pins, key=lambda item: item.pin.casefold()):
                nets = pin_nets[load.pin]
                if len(nets) == 1 and nets[0].casefold() != output_nets[0].casefold():
                    issues.append(
                        f"direct load {load.pin} is on {nets[0]}; "
                        f"oscillator output is on {output_nets[0]}"
                    )
    else:
        output_nets = pin_nets[requirement.output_pin]
        resistor_output_nets = pin_nets[resistor.output_side_pin]
        resistor_load_nets = pin_nets[resistor.load_side_pin]
        if len(output_nets) == len(resistor_output_nets) == 1 and (
            output_nets[0].casefold() != resistor_output_nets[0].casefold()
        ):
            issues.append(
                f"{resistor.output_side_pin} is not on oscillator output net {output_nets[0]}"
            )
        if len(resistor_load_nets) == 1:
            if len(output_nets) == 1 and (
                resistor_load_nets[0].casefold() == output_nets[0].casefold()
            ):
                issues.append("mapped series resistor does not separate output and load nets")
            for load in sorted(requirement.load_pins, key=lambda item: item.pin.casefold()):
                nets = pin_nets[load.pin]
                if len(nets) == 1 and nets[0].casefold() != resistor_load_nets[0].casefold():
                    issues.append(
                        f"series load {load.pin} is on {nets[0]}; "
                        f"resistor load side is on {resistor_load_nets[0]}"
                    )
        if len(output_nets) == len(resistor_load_nets) == 1:
            expected_nets = {output_nets[0].casefold(), resistor_load_nets[0].casefold()}
            expected_resistor = resistor.reference.casefold()
            for candidate in direct_resistors(observed, include_zero_ohm=True):
                if (
                    candidate.reference.casefold() != expected_resistor
                    and {candidate.first_net.casefold(), candidate.second_net.casefold()}
                    == expected_nets
                ):
                    issues.append(
                        f"unmapped fitted resistor {candidate.reference} also bridges "
                        f"oscillator output net {output_nets[0]} and load net "
                        f"{resistor_load_nets[0]} alongside mapped series resistor "
                        f"{resistor.reference}"
                    )
        component = _lookup(observed.components, resistor.reference)
        if component is not None:
            measured = resistance_ohms(component.value)
            if measured is None:
                issues.append(
                    f"{resistor.reference} value {component.value!r} is not a supported "
                    "resistance spelling"
                )
            elif not (
                resistor.minimum_nominal_resistance_ohms
                <= measured
                <= resistor.maximum_nominal_resistance_ohms
            ):
                issues.append(
                    f"{resistor.reference} nominal resistance is {measured:g} ohms; "
                    f"reviewed range is {resistor.minimum_nominal_resistance_ohms:g}–"
                    f"{resistor.maximum_nominal_resistance_ohms:g} ohms"
                )
    return tuple(dict.fromkeys(issues))


def oscillator_output_path_mismatches(
    path_map: OscillatorOutputPathMap,
    observed: NetlistContract,
) -> tuple[OscillatorOutputPathMismatch, ...]:
    """Check authored direct or series output topology and nominal resistor bounds."""
    mismatches: list[OscillatorOutputPathMismatch] = []
    for requirement in sorted(path_map.paths, key=lambda item: item.id.casefold()):
        issues = _path_issues(requirement, observed)
        if not issues:
            continue
        resistor = requirement.series_resistor
        mismatches.append(
            OscillatorOutputPathMismatch(
                path_id=requirement.id,
                basis=requirement.basis,
                oscillator_output_pin=requirement.output_pin,
                topology=requirement.topology,
                load_pins=tuple(
                    sorted((item.pin for item in requirement.load_pins), key=str.casefold)
                ),
                series_resistor=None if resistor is None else resistor.reference,
                issues=issues,
            )
        )
    return tuple(mismatches)
