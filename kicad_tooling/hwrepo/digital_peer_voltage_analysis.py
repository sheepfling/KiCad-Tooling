"""Recognize digital peer roles and voltage-named supply clues."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from .digital_peer_voltage_types import DigitalPeerLink, VoltageNamedRail
from .models import DigitalPeerPinRequirement, DigitalPeerVoltageAnalysis, NetlistContract
from .return_nets import is_return_like_net_name
from .serial_participants import serial_function_role_and_channel

IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)

_SPI_CLOCK = frozenset({"sck", "sclk"})

_SPI_DATA = frozenset({"mosi", "sdi", "copi", "miso", "sdo", "cipo"})

_SPI_SELECT = frozenset({"cs", "csn", "ncs", "nss", "ss", "ssel", "ce0", "ce1"})

_SPI_FUNCTIONS = _SPI_CLOCK | _SPI_DATA | _SPI_SELECT

OUTPUT_TYPES = frozenset({"output", "tri_state", "bidirectional"})

INPUT_TYPES = frozenset({"input", "bidirectional"})

_RAIL_TOKEN = re.compile(
    r"(?<![A-Z0-9+-])\+?(?P<whole>\d+)"
    r"(?:V(?P<suffix_fraction>\d+)|\.(?P<decimal_fraction>\d+)V|V)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


def canonical_spi_function(value: str) -> str:
    function = re.sub(r"[^a-z0-9]", "", value.casefold())
    if function.startswith("spi"):
        function = function[3:].lstrip("0123456789")
    return function


def interface_and_role(
    value: str,
) -> tuple[Literal["SPI", "serial"], str | None] | None:
    if canonical_spi_function(value) in _SPI_FUNCTIONS:
        return "SPI", None
    role_channel = serial_function_role_and_channel(value)
    if role_channel is not None:
        return "serial", role_channel[0]
    return None


def nominal_voltage_from_net_name(name: str) -> Decimal | None:
    """Read only explicit positive-voltage tokens; names remain review clues."""
    matches = tuple(_RAIL_TOKEN.finditer(name))
    if len(matches) != 1:
        return None
    match = matches[0]
    whole = Decimal(match.group("whole"))
    suffix_fraction = match.group("suffix_fraction")
    decimal_fraction = match.group("decimal_fraction")
    fraction = suffix_fraction or decimal_fraction
    if fraction is not None:
        whole += Decimal(fraction).scaleb(-len(fraction))
    if whole <= 0:
        return None
    return whole.normalize()


def pin_assignment_index(
    observed: NetlistContract,
) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    references = {reference.casefold(): reference for reference in observed.components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    return pin_nets, references, symbols


def is_return_assignment(net: str, function: str) -> bool:
    """Recognize return labels and functions with optional trailing pin indices."""
    return any(
        is_return_like_net_name(re.sub(r"\d+$", "", value.strip())) for value in (net, function)
    )


def unambiguous_voltage_named_supply(
    reference: str,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
) -> VoltageNamedRail | None:
    """Require complete native pin types and exactly one assigned positive rail."""
    reference_key = reference.casefold()
    pin_numbers = next(
        (
            numbers
            for component, numbers in observed.component_pin_numbers.items()
            if component.casefold() == reference_key
        ),
        (),
    )
    if not pin_numbers:
        return None

    types = {
        pin.casefold(): pin_type.casefold()
        for pin, pin_type in observed.pin_electrical_types.items()
    }
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    if any(f"{reference}.{number}".casefold() not in types for number in pin_numbers):
        return None

    assigned_positive: dict[str, Decimal] = {}
    found_power_input = False
    for number in pin_numbers:
        pin = f"{reference}.{number}"
        if types.get(pin.casefold()) != "power_in":
            continue
        found_power_input = True
        nets = pin_nets.get(pin.casefold(), set())
        if len(nets) != 1:
            return None
        net = next(iter(nets))
        if is_return_assignment(net, functions.get(pin.casefold(), "")):
            continue
        nominal = nominal_voltage_from_net_name(net)
        if nominal is None:
            return None
        assigned_positive[net] = nominal

    if not found_power_input or len(assigned_positive) != 1:
        return None
    net, voltage = next(iter(assigned_positive.items()))
    return VoltageNamedRail(net=net, voltage_v=voltage)


def endpoint_matches_native(
    endpoint: DigitalPeerPinRequirement,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
) -> bool:
    reference = endpoint.reference
    reference_key = reference.casefold()
    canonical_reference = references.get(reference_key)
    if canonical_reference is None or canonical_reference.casefold() in {
        item.casefold() for item in observed.dnp_components
    }:
        return False
    component = next(
        (
            item
            for component_reference, item in observed.components.items()
            if component_reference.casefold() == reference_key
        ),
        None,
    )
    if (
        component is None
        or symbols.get(reference_key) != endpoint.symbol
        or component.footprint != endpoint.footprint
    ):
        return False
    pin = endpoint.pin
    net = endpoint.net
    return pin_nets.get(pin.casefold(), set()) == {net}


def fully_mapped_link(
    link: DigitalPeerLink,
    analysis: DigitalPeerVoltageAnalysis | None,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
) -> bool:
    if analysis is None:
        return False
    for reviewed in analysis.links:
        output_limits = reviewed.output_limits
        input_limits = reviewed.input_limits
        driver = reviewed.driver
        receiver = reviewed.receiver
        if output_limits is None or input_limits is None:
            continue
        if (
            driver.reference.casefold() != link.output_reference.casefold()
            or driver.pin.casefold() != link.output_pin.casefold()
            or receiver.reference.casefold() != link.input_reference.casefold()
            or receiver.pin.casefold() != link.input_pin.casefold()
            or driver.net != link.net
            or receiver.net != link.net
        ):
            continue
        if endpoint_matches_native(
            driver, observed, pin_nets, references, symbols
        ) and endpoint_matches_native(receiver, observed, pin_nets, references, symbols):
            return True
    return False
