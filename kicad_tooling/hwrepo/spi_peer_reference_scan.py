"""Find direct SPI clock peers with different explicit reference nets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .digital_peer_voltage_analysis import INPUT_TYPES, OUTPUT_TYPES, canonical_spi_function
from .models import NetlistContract
from .return_nets import is_return_like_net_name

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_NON_SIGNAL_REFERENCE = re.compile(
    r"(?:^|[^A-Z0-9])(?:CHASSIS|SHIELD|FRAME|PE)(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)
_REFERENCE_PIN_TYPES = frozenset({"passive", "power_in"})
_CLOCK_PIN_TYPES = OUTPUT_TYPES | INPUT_TYPES


@dataclass(frozen=True)
class SpiReferencePinAssignment:
    """One explicitly assigned return-like pin from a complete native inventory."""

    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class SpiClockEndpoint:
    """One fitted IC with one assigned native SCK/SCLK function."""

    reference: str
    clock_pin: str
    clock_type: str
    clock_net: str
    reference_net: str | None
    reference_pins: tuple[SpiReferencePinAssignment, ...]


@dataclass(frozen=True)
class SpiClockPeerBus:
    """Coverage state for fitted ICs sharing one exact native clock net."""

    clock_net: str
    endpoints: tuple[SpiClockEndpoint, ...]
    incomplete_references: tuple[str, ...]
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
    ]


@dataclass(frozen=True)
class SpiPeerReferenceScan:
    """Supported SPI clock endpoints and shared-clock reference states."""

    recognized_endpoint_count: int
    buses: tuple[SpiClockPeerBus, ...]

    @property
    def reviews(self) -> tuple[SpiClockPeerBus, ...]:
        return tuple(
            bus
            for bus in self.buses
            if bus.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        )


def _reference_assignments(
    reference: str,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    pin_numbers: tuple[str, ...],
) -> tuple[str | None, tuple[SpiReferencePinAssignment, ...]]:
    if not pin_numbers:
        return None, ()
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    assignments: list[SpiReferencePinAssignment] = []
    for number in pin_numbers:
        pin = f"{reference}.{number}"
        pin_key = pin.casefold()
        function = functions.get(pin_key)
        electrical_type = electrical_types.get(pin_key)
        if function is None or electrical_type is None:
            return None, ()
        if _NON_SIGNAL_REFERENCE.search(function) or not is_return_like_net_name(function):
            continue
        if electrical_type not in _REFERENCE_PIN_TYPES:
            return None, ()
        nets = pin_nets.get(pin_key, set())
        if len(nets) != 1:
            return None, ()
        assignments.append(
            SpiReferencePinAssignment(
                pin=pin,
                function=function,
                electrical_type=electrical_type,
                net=next(iter(nets)),
            )
        )
    if not assignments:
        return None, ()
    reference_nets = {item.net.casefold() for item in assignments}
    ordered = tuple(sorted(assignments, key=lambda item: item.pin.casefold()))
    if len(reference_nets) != 1:
        return None, ordered
    return ordered[0].net, ordered


def scan_spi_peer_references(observed: NetlistContract) -> SpiPeerReferenceScan:
    """Review separate explicit references among fitted ICs sharing native SCK.

    The predicate requires one assigned SCK/SCLK pin per endpoint, compatible
    native input/output types across the shared clock net, a complete native
    pin-number inventory, and explicit passive or power-input return pins.
    It does not infer common-reference intent from names or trace translated,
    isolated, off-board, or PCB-copper paths.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    pin_numbers = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    endpoints: list[SpiClockEndpoint] = []
    for reference in sorted(observed.components, key=lambda item: (item.casefold(), item)):
        reference_key = reference.casefold()
        if not _IC_REFERENCE.fullmatch(reference) or reference_key in dnp:
            continue
        known_numbers = {number.casefold() for number in pin_numbers.get(reference_key, ())}
        clock_pins: list[tuple[str, str, str]] = []
        for pin_key, function in functions.items():
            pin_reference, separator, number = pin_key.rpartition(".")
            if (
                not separator
                or pin_reference != reference_key
                or number not in known_numbers
                or canonical_spi_function(function) not in {"sck", "sclk"}
            ):
                continue
            assigned = pin_nets.get(pin_key, set())
            electrical_type = electrical_types.get(pin_key)
            if len(assigned) != 1 or electrical_type not in _CLOCK_PIN_TYPES:
                continue
            clock_pins.append((f"{reference}.{number}", next(iter(assigned)), electrical_type))
        if len(clock_pins) != 1:
            continue
        clock_pin, clock_net, clock_type = clock_pins[0]
        reference_net, reference_pins = _reference_assignments(
            reference,
            observed,
            pin_nets,
            pin_numbers.get(reference_key, ()),
        )
        endpoints.append(
            SpiClockEndpoint(
                reference=reference,
                clock_pin=clock_pin,
                clock_type=clock_type,
                clock_net=clock_net,
                reference_net=reference_net,
                reference_pins=reference_pins,
            )
        )

    grouped: dict[str, list[SpiClockEndpoint]] = {}
    for endpoint in endpoints:
        grouped.setdefault(endpoint.clock_net.casefold(), []).append(endpoint)

    buses: list[SpiClockPeerBus] = []
    for endpoints_on_clock in grouped.values():
        if len(endpoints_on_clock) < 2:
            continue
        has_clock_output = any(item.clock_type in OUTPUT_TYPES for item in endpoints_on_clock)
        has_clock_input = any(item.clock_type in INPUT_TYPES for item in endpoints_on_clock)
        if not has_clock_output or not has_clock_input:
            continue
        ordered = tuple(
            sorted(endpoints_on_clock, key=lambda item: (item.reference.casefold(), item.reference))
        )
        reference_nets = {
            item.reference_net.casefold() for item in ordered if item.reference_net is not None
        }
        incomplete = tuple(item.reference for item in ordered if item.reference_net is None)
        if len(reference_nets) > 1:
            disposition = (
                "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete else "SPLIT_REFERENCE_REVIEW"
            )
        elif incomplete:
            disposition = "INCOMPLETE"
        else:
            disposition = "COMMON_REFERENCE"
        buses.append(
            SpiClockPeerBus(
                clock_net=ordered[0].clock_net,
                endpoints=ordered,
                incomplete_references=incomplete,
                disposition=disposition,
            )
        )

    return SpiPeerReferenceScan(
        recognized_endpoint_count=len(endpoints),
        buses=tuple(sorted(buses, key=lambda item: (item.clock_net.casefold(), item.clock_net))),
    )
