"""Review candidates for likely SPI peripherals missing from the project roster."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import NetlistContract
from .spi_models import SpiAnalysis

_SPI_DEVICE_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_SPI_CLOCK_FUNCTIONS = {"sck", "sclk"}
_SPI_INPUT_DATA_FUNCTIONS = {"mosi", "sdi", "copi"}
_SPI_OUTPUT_DATA_FUNCTIONS = {"miso", "sdo", "cipo"}
_SPI_SELECT_FUNCTIONS = {
    "cs",
    "csn",
    "ncs",
    "nss",
    "ss",
    "ssn",
    "ssel",
    "ce0",
    "ce1",
    "chipselect",
    "chipselectn",
}

SpiRosterState = Literal["not_configured", "pending", "not_applicable", "required"]


@dataclass(frozen=True)
class SpiRosterContext:
    """Authored SPI membership state and its source binding for one lint run."""

    state: SpiRosterState
    analysis: SpiAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class UnmappedSpiParticipant:
    """Likely SPI-capable IC with connected clock/data pins absent from the roster."""

    reference: str
    clock_pins: tuple[str, ...]
    input_data_pins: tuple[str, ...]
    output_data_pins: tuple[str, ...]
    chip_select_pins: tuple[str, ...]
    signal_assignments: tuple[str, ...]


def _canonical_function_and_channel(value: str) -> tuple[str, str]:
    """Normalize an SPI pin function and retain an optional numeric channel."""
    function = re.sub(r"[^a-z0-9]", "", value.casefold())
    channel = "default"
    if function.startswith("spi"):
        function = function[3:]
        match = re.match(r"^(\d+)(.*)$", function)
        if match is not None:
            channel = f"index{match.group(1)}"
            function = match.group(2)
    return function, channel


def _canonical_function(value: str) -> str:
    """Normalize exact SPI pin-function aliases without inspecting part names."""
    function, _channel = _canonical_function_and_channel(value)
    return function


def spi_data_function_role_and_channel(value: str) -> tuple[str, str] | None:
    """Recognize bounded SPI data aliases while preserving an optional channel index."""
    function, channel = _canonical_function_and_channel(value)
    if function in _SPI_INPUT_DATA_FUNCTIONS:
        return "input", channel
    if function in _SPI_OUTPUT_DATA_FUNCTIONS:
        return "output", channel
    return None


def spi_signal_role_and_channel(value: str) -> tuple[str, str] | None:
    """Recognize bounded SPI clock, data, and chip-select roles with channel identity."""
    data_role = spi_data_function_role_and_channel(value)
    if data_role is not None:
        direction, channel = data_role
        return f"data_{direction}", channel

    function, channel = _canonical_function_and_channel(value)
    if function in _SPI_CLOCK_FUNCTIONS:
        return "clock", channel
    if function in _SPI_SELECT_FUNCTIONS:
        return "chip_select", channel
    return None


def is_spi_ic_reference(reference: str) -> bool:
    """Return whether a reference follows the bounded fitted IC convention."""
    return _SPI_DEVICE_REFERENCE.fullmatch(reference) is not None


def is_spi_chip_select_function(function: str) -> bool:
    """Recognize bounded chip-select aliases, including indexed SPI NSS names."""
    return _canonical_function(function) in _SPI_SELECT_FUNCTIONS


def is_spi_data_output_function(function: str) -> bool:
    """Recognize bounded SPI peripheral-to-controller data pin aliases."""
    role_channel = spi_data_function_role_and_channel(function)
    return role_channel is not None and role_channel[0] == "output"


def _mapped_references(analysis: SpiAnalysis | None) -> set[str]:
    if analysis is None:
        return set()
    return {
        reference.casefold()
        for bus in analysis.buses
        for reference in (
            bus.controller.reference,
            *(device.reference for device in bus.devices),
            *(bridge.reference for bridge in bus.bridges),
        )
    }


def unmapped_spi_participants(
    observed: NetlistContract,
    roster: SpiRosterContext,
) -> tuple[UnmappedSpiParticipant, ...]:
    """Find connected SPI-like ICs absent from the independently authored roster.

    This is a review-only coverage prompt. It uses exact exported symbol pin
    functions and assigned nets; it does not infer intent from component values,
    footprint names, or net labels. A project roster covers references even if
    its separate source-bound comparison reports wrong pin mappings.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    references = {reference.casefold(): reference for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    mapped_references = _mapped_references(roster.analysis)
    by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    select_pins: dict[str, set[str]] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        if not separator:
            continue
        canonical_reference = references.get(reference.casefold())
        if canonical_reference is None or not is_spi_ic_reference(canonical_reference):
            continue
        reference_key = canonical_reference.casefold()
        if reference_key in dnp_references or reference_key in mapped_references:
            continue

        role = _canonical_function(function)
        if is_spi_chip_select_function(function):
            select_pins.setdefault(reference_key, set()).add(pin)
            continue
        if role not in (
            _SPI_CLOCK_FUNCTIONS | _SPI_INPUT_DATA_FUNCTIONS | _SPI_OUTPUT_DATA_FUNCTIONS
        ):
            continue
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
            (pin, next(iter(assigned_nets)))
        )

    findings: list[UnmappedSpiParticipant] = []
    for reference_key, role_pins in sorted(by_reference.items()):
        clocks = sorted(
            item
            for role, items in role_pins.items()
            if role in _SPI_CLOCK_FUNCTIONS
            for item in items
        )
        inputs = sorted(
            item
            for role, items in role_pins.items()
            if role in _SPI_INPUT_DATA_FUNCTIONS
            for item in items
        )
        outputs = sorted(
            item
            for role, items in role_pins.items()
            if role in _SPI_OUTPUT_DATA_FUNCTIONS
            for item in items
        )
        selects = tuple(sorted(select_pins.get(reference_key, ())))
        if not clocks or not (inputs or outputs) or not selects:
            continue

        reference = references[reference_key]
        assignments = tuple(sorted({f"{pin}={net}" for pin, net in (*clocks, *inputs, *outputs)}))
        findings.append(
            UnmappedSpiParticipant(
                reference=reference,
                clock_pins=tuple(pin for pin, _net in clocks),
                input_data_pins=tuple(pin for pin, _net in inputs),
                output_data_pins=tuple(pin for pin, _net in outputs),
                chip_select_pins=selects,
                signal_assignments=assignments,
            )
        )

    return tuple(findings)
