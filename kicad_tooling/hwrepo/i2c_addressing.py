"""Project-authored I2C address maps checked against native netlist evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import (
    I2cAddressBitEvidence,
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cResponderAddressCoverageEntry,
    I2cResponderAddressRequirement,
    NetlistContract,
)

_I2C_ADDRESS_DEVICE_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_I2C_ADDRESS_PIN_ROLES = {
    "sda": "SDA",
    "i2csda": "SDA",
    "scl": "SCL",
    "i2cscl": "SCL",
}


@dataclass(frozen=True)
class UnmappedI2cResponder:
    """Likely I2C IC candidate not listed in the project-authored address map."""

    reference: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]
    signal_pairs: tuple[tuple[str, str], ...]


def unmapped_i2c_responders(
    observed: NetlistContract,
    specification: I2cAddressMap | None,
) -> tuple[UnmappedI2cResponder, ...]:
    """Find U/IC references with assigned SDA/SCL functions missing from the map.

    This deliberately uses symbol pin functions rather than part values or net
    spelling. It is a review candidate: the native netlist cannot establish
    whether a part is an addressable responder, or whether the function metadata
    is correct.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    mapped_references: set[str] = (
        {
            responder.reference.casefold()
            for segment in specification.segments
            for responder in segment.responders
        }
        if specification is not None
        else set()
    )
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    functions_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    references = {reference.casefold(): reference for reference in observed.component_symbols}

    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        if not separator:
            continue
        canonical_reference = references.get(reference.casefold())
        if canonical_reference is None or not _I2C_ADDRESS_DEVICE_REFERENCE.fullmatch(
            canonical_reference
        ):
            continue
        role_key = re.sub(r"[^a-z0-9]", "", function.casefold())
        role = _I2C_ADDRESS_PIN_ROLES.get(role_key)
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if role is None or len(assigned_nets) != 1:
            continue
        functions_by_reference.setdefault(canonical_reference, {}).setdefault(role, []).append(
            (pin, next(iter(assigned_nets)))
        )

    findings: list[UnmappedI2cResponder] = []
    for reference, roles in sorted(functions_by_reference.items()):
        reference_key = reference.casefold()
        if reference_key in mapped_references or reference_key in dnp_references:
            continue
        sda = sorted(roles.get("SDA", ()))
        scl = sorted(roles.get("SCL", ()))
        if not sda or not scl:
            continue
        pairs = tuple(
            sorted(
                {
                    (sda_net, scl_net)
                    for _sda_pin, sda_net in sda
                    for _scl_pin, scl_net in scl
                    if sda_net.casefold() != scl_net.casefold()
                }
            )
        )
        if not pairs:
            continue
        findings.append(
            UnmappedI2cResponder(
                reference=reference,
                sda_pins=tuple(pin for pin, _net in sda),
                scl_pins=tuple(pin for pin, _net in scl),
                signal_pairs=pairs,
            )
        )
    return tuple(findings)


def _format_nets(nets: tuple[str, ...]) -> str:
    return ", ".join(nets) if nets else "unconnected"


def _address_entry(
    segment_id: str,
    segment_sda: str,
    segment_scl: str,
    requirement: I2cResponderAddressRequirement,
    component_references: set[str],
    nets_by_pin: dict[str, set[str]],
    symbols_by_reference: dict[str, str],
    pin_functions: dict[str, str],
    known_pins: set[str],
    pin_numbers: dict[str, set[str]],
    dnp_references: set[str],
) -> I2cResponderAddressCoverageEntry:
    reference_key = requirement.reference.casefold()
    observed_symbol = symbols_by_reference.get(reference_key)
    issues: list[str] = []
    if reference_key not in component_references:
        issues.append(f"{requirement.reference} is absent from the native netlist")
    if observed_symbol != requirement.expected_symbol:
        issues.append(
            f"symbol is {observed_symbol or 'unknown'}; expected {requirement.expected_symbol}"
        )

    def endpoint_nets(pin: str, role: str, expected_net: str) -> tuple[str, ...]:
        pin_key = pin.casefold()
        if (
            reference_key not in pin_numbers
            or pin.rsplit(".", 1)[1].casefold() not in pin_numbers[reference_key]
        ):
            issues.append(f"{role} pin {pin} is absent from the native symbol pin inventory")
        elif pin_key not in known_pins:
            issues.append(f"{role} pin {pin} has no native pin evidence")
        assigned = tuple(sorted(nets_by_pin.get(pin_key, ())))
        if assigned != (expected_net,):
            issues.append(
                f"{role} pin {pin} is on {_format_nets(assigned)}; expected {expected_net}"
            )
        return assigned

    sda_nets = endpoint_nets(requirement.sda_pin, "SDA", segment_sda)
    scl_nets = endpoint_nets(requirement.scl_pin, "SCL", segment_scl)

    address_bits: list[I2cAddressBitEvidence] = []
    actual_address = requirement.address
    address_resolved = requirement.mode != "dynamic"
    for bit in requirement.address_bits:
        pin_key = bit.pin.casefold()
        pin_number = bit.pin.rsplit(".", 1)[1].casefold()
        if reference_key not in pin_numbers or pin_number not in pin_numbers[reference_key]:
            issues.append(f"address pin {bit.pin} is absent from the native symbol pin inventory")
        elif pin_key not in known_pins:
            issues.append(f"address pin {bit.pin} has no native pin evidence")

        observed_function = pin_functions.get(pin_key)
        if observed_function is None:
            issues.append(f"address pin {bit.pin} has no exported symbol function")
        elif observed_function.strip().casefold() != bit.function.strip().casefold():
            issues.append(
                f"address pin {bit.pin} function is {observed_function}; expected {bit.function}"
            )

        assigned = tuple(sorted(nets_by_pin.get(pin_key, ())))
        resolved_value: int | None = None
        if assigned == (bit.low_net,):
            resolved_value = 0
        elif assigned == (bit.high_net,):
            resolved_value = 1
        else:
            issues.append(
                f"address pin {bit.pin} is on {_format_nets(assigned)}; expected "
                f"{bit.low_net} for 0 or {bit.high_net} for 1"
            )
        address_bits.append(
            I2cAddressBitEvidence(
                bit=bit.bit,
                pin=bit.pin,
                expected_function=bit.function,
                observed_function=observed_function,
                nets=assigned,
                resolved_value=resolved_value,
            )
        )
        if resolved_value is None:
            address_resolved = False
        elif actual_address is not None:
            mask = 1 << bit.bit
            actual_address = (actual_address & ~mask) | (resolved_value << bit.bit)

    if requirement.mode == "dynamic":
        status = "INCOMPLETE" if issues else "DYNAMIC"
        actual_address = None
        if not issues:
            issues.append("address is dynamic and cannot be checked for static collisions")
    else:
        if not address_resolved:
            actual_address = None
        status = "COMPLETE" if not issues and actual_address is not None else "INCOMPLETE"

    if reference_key in dnp_references:
        status = "INCOMPLETE" if issues else "NOT_FITTED"
        actual_address = None

    return I2cResponderAddressCoverageEntry(
        reference=requirement.reference,
        segment_id=segment_id,
        status=status,
        mode=requirement.mode,
        expected_symbol=requirement.expected_symbol,
        observed_symbol=observed_symbol,
        sda_pin=requirement.sda_pin,
        scl_pin=requirement.scl_pin,
        sda_nets=sda_nets,
        scl_nets=scl_nets,
        expected_address=requirement.address,
        observed_address=actual_address,
        address_bits=tuple(address_bits),
        basis=requirement.basis,
        issues=tuple(issues),
    )


def scan_i2c_address_map(
    specification: I2cAddressMap,
    observed: NetlistContract,
    netlist_sha256: str,
) -> I2cAddressCoverageReport:
    """Resolve configured static addresses without guessing device pin roles."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    symbols_by_reference = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    component_references = {reference.casefold() for reference in observed.components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    known_pins = {
        *(pin.casefold() for pin in observed.pin_functions),
        *(pin.casefold() for pin in observed.pin_electrical_types),
        *(pin.casefold() for pins in observed.nets.values() for pin in pins),
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}

    entries = tuple(
        _address_entry(
            segment.id,
            segment.sda_net,
            segment.scl_net,
            responder,
            component_references,
            nets_by_pin,
            symbols_by_reference,
            pin_functions,
            known_pins,
            pin_numbers,
            dnp_references,
        )
        for segment in specification.segments
        for responder in segment.responders
    )
    issues = tuple(
        f"{entry.reference} on segment {entry.segment_id}: {issue}"
        for entry in entries
        for issue in entry.issues
    )
    complete_statuses = {"COMPLETE", "NOT_FITTED"}
    status = (
        "COMPLETE" if all(entry.status in complete_statuses for entry in entries) else "INCOMPLETE"
    )
    return I2cAddressCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        entries=entries,
        issues=issues,
    )
