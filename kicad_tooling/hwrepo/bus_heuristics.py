"""Reviewable two-wire bus topology hints from a native KiCad netlist."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from .connector_pins import power_function_key
from .crystal_networks import parse_capacitance_pf
from .models import (
    AnalysisPending,
    CanTerminationAnalysis,
    CanTerminationMidpointCapacitorRequirement,
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    ComponentContract,
    ElectricalCheck,
    I2cPullupAnalysis,
    I2cPullupArrayRequirement,
    I2cPullupHeuristicCoverage,
    I2cPullupHeuristicEntry,
    I2cPullupLineRequirement,
    I2cPullupSeriesPathRequirement,
    I2cPullupVoltageCompatibilityRequirement,
    NetlistContract,
    SpiAnalysis,
    SpiBridgeRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
    SpiPinNotPresent,
    SpiPinUnconnectedRequirement,
    UsbCAnalysis,
    UsbCcResistorAttachment,
    UsbCProtectionAnalysis,
    UsbCVbusCapacitanceRequirement,
    UsbCVbusPathRequirement,
)
from .return_nets import is_return_like_net_name

_I2C_FUNCTIONS = {
    "sda": "SDA",
    "i2csda": "SDA",
    "scl": "SCL",
    "i2cscl": "SCL",
}
_CAN_FUNCTIONS = {
    "canh": "CANH",
    "canhigh": "CANH",
    "canl": "CANL",
    "canlow": "CANL",
}
_COMPLEMENTARY_FUNCTIONS: dict[str, tuple[str, str]] = {
    "canh": ("CAN", "positive"),
    "canhigh": ("CAN", "positive"),
    "canl": ("CAN", "negative"),
    "canlow": ("CAN", "negative"),
    "d+": ("USB data", "positive"),
    "dp": ("USB data", "positive"),
    "dplus": ("USB data", "positive"),
    # DP1/DM1 are single-port aliases here. The USB peer-reference review
    # keeps DPn/DMn port groups in its own typed topology model.
    "dp1": ("USB data", "positive"),
    "ud+": ("USB data", "positive"),
    "usbd+": ("USB data", "positive"),
    "usbdp": ("USB data", "positive"),
    "usbdplus": ("USB data", "positive"),
    "d-": ("USB data", "negative"),
    "dm": ("USB data", "negative"),
    "dminus": ("USB data", "negative"),
    "dm1": ("USB data", "negative"),
    "ud-": ("USB data", "negative"),
    "usbd-": ("USB data", "negative"),
    "usbdm": ("USB data", "negative"),
    "usbdminus": ("USB data", "negative"),
    "tx+": ("TX", "positive"),
    "txp": ("TX", "positive"),
    "txplus": ("TX", "positive"),
    "tx-": ("TX", "negative"),
    "txn": ("TX", "negative"),
    "txminus": ("TX", "negative"),
    "rx+": ("RX", "positive"),
    "rxp": ("RX", "positive"),
    "rxplus": ("RX", "positive"),
    "rx-": ("RX", "negative"),
    "rxn": ("RX", "negative"),
    "rxminus": ("RX", "negative"),
    "sstx+": ("USB SuperSpeed TX", "positive"),
    "sstx-": ("USB SuperSpeed TX", "negative"),
    "stdasstx+": ("USB SuperSpeed TX", "positive"),
    "stdasstx-": ("USB SuperSpeed TX", "negative"),
    "stdbsstx+": ("USB SuperSpeed TX", "positive"),
    "stdbsstx-": ("USB SuperSpeed TX", "negative"),
    "ssrx+": ("USB SuperSpeed RX", "positive"),
    "ssrx-": ("USB SuperSpeed RX", "negative"),
    "stdassrx+": ("USB SuperSpeed RX", "positive"),
    "stdassrx-": ("USB SuperSpeed RX", "negative"),
    "stdbssrx+": ("USB SuperSpeed RX", "positive"),
    "stdbssrx-": ("USB SuperSpeed RX", "negative"),
}
_SPI_CHIP_SELECT_FUNCTIONS = frozenset(
    {"cs", "csn", "ncs", "nss", "ss", "ssn", "chipselect", "chipselectn"}
)
_SPI_ACTIVE_LOW_CHIP_SELECT_FUNCTIONS = frozenset({"csn", "ncs", "nss", "ssn", "chipselectn"})
_RESISTOR_REFERENCE = re.compile(r"^R[A-Z]*[0-9]+$", re.IGNORECASE)
_ENGINEERING_VALUE = re.compile(r"^(?P<whole>[0-9]+)(?P<unit>[krm])(?P<fraction>[0-9]+)$")
_STANDARD_VALUE = re.compile(r"^(?P<amount>[0-9]+(?:\.[0-9]+)?)(?P<unit>[krm]?)$")


@dataclass(frozen=True)
class I2cPullupGap:
    sda_net: str
    scl_net: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]
    missing_lines: tuple[Literal["SDA", "SCL"], ...]


@dataclass(frozen=True)
class I2cLowEquivalentResistance:
    sda_net: str
    scl_net: str
    lines: tuple[str, ...]
    pins: dict[str, tuple[str, ...]]
    resistors: dict[str, tuple[str, ...]]
    equivalent_ohms: dict[str, str]


@dataclass(frozen=True)
class I2cMultiplePullupRailFamilies:
    sda_net: str
    scl_net: str
    pins: tuple[str, ...]
    rail_families: tuple[str, ...]
    pullup_paths: tuple[str, ...]


@dataclass(frozen=True)
class VisiblePullupPath:
    references: tuple[str, ...]
    resistance_ohms: float
    rail_net: str


@dataclass(frozen=True)
class SpiChipSelectBiasGap:
    net: str
    pins: tuple[str, ...]
    positive_rails: tuple[str, ...]


@dataclass(frozen=True)
class DirectResistor:
    reference: str
    resistance_ohms: float
    first_net: str
    second_net: str


@dataclass(frozen=True)
class CanTerminationGap:
    high_net: str
    low_net: str
    high_pins: tuple[str, ...]
    low_pins: tuple[str, ...]


@dataclass(frozen=True)
class CanPeerAssignmentDivergence:
    """Complete CAN pin pairs that share one side but disagree on the other."""

    shared_role: Literal["CANH", "CANL"]
    shared_net: str
    complementary_role: Literal["CANH", "CANL"]
    complementary_nets: tuple[str, ...]
    participants: tuple[str, ...]


@dataclass(frozen=True)
class UnconnectedInterfacePin:
    protocol: Literal["i2c", "spi", "usb_c", "can"]
    pin: str
    function: str


@dataclass(frozen=True)
class ComplementaryLineGap:
    reference: str
    family: str
    reason: str
    pins: dict[str, tuple[str, ...]]
    nets: dict[str, tuple[str, ...]]
    alias_symbol: str | None = None
    alias_basis: str | None = None
    alias_sha256: str | None = None


@dataclass(frozen=True)
class ComplementaryPinFunctionAliasResolution:
    by_symbol: dict[str, tuple[ComplementaryPinFunctionAlias, ...]]
    issues: tuple[str, ...] = ()


def _complementary_function_key(function: str) -> str:
    return re.sub(r"[\s_./]", "", function.casefold()).replace("−", "-")


def _complementary_alias_sha256(alias: ComplementaryPinFunctionAlias) -> str:
    payload = {
        "symbol": alias.symbol,
        "family": alias.family,
        "positive_functions": sorted(
            {_complementary_function_key(item) for item in alias.positive_functions}
        ),
        "negative_functions": sorted(
            {_complementary_function_key(item) for item in alias.negative_functions}
        ),
        "basis": alias.basis,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_complementary_pin_function_aliases(
    observed: NetlistContract,
    specification: ComplementaryPinFunctionAliasMap | None,
) -> ComplementaryPinFunctionAliasResolution:
    """Resolve opt-in aliases only against the exact native symbol and pin functions."""
    if specification is None:
        return ComplementaryPinFunctionAliasResolution(by_symbol={})

    symbols = set(observed.component_symbols.values())
    functions_by_symbol: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        if not separator:
            continue
        symbol = observed.component_symbols.get(reference)
        if symbol is not None:
            functions_by_symbol.setdefault(symbol, set()).add(_complementary_function_key(function))

    resolved: dict[str, list[ComplementaryPinFunctionAlias]] = {}
    issues: list[str] = []
    for alias in specification.entries:
        if alias.symbol not in symbols:
            issues.append(
                f"Complementary pin-function alias for {alias.symbol!r} has no exact native symbol instance."
            )
            continue
        builtin_aliases = sorted(
            {
                _complementary_function_key(function)
                for function in (*alias.positive_functions, *alias.negative_functions)
                if _complementary_function_key(function) in _COMPLEMENTARY_FUNCTIONS
            }
        )
        if builtin_aliases:
            issues.append(
                f"Complementary pin-function alias for {alias.symbol!r} repeats built-in function alias(es): "
                f"{', '.join(builtin_aliases)}."
            )
            continue
        expected = {
            _complementary_function_key(function)
            for function in (*alias.positive_functions, *alias.negative_functions)
        }
        if not expected & functions_by_symbol.get(alias.symbol, set()):
            issues.append(
                f"Complementary pin-function alias for {alias.symbol!r} is stale: none of its configured "
                "functions occur in the native symbol pin inventory."
            )
            continue
        resolved.setdefault(alias.symbol, []).append(alias)
    return ComplementaryPinFunctionAliasResolution(
        by_symbol={symbol: tuple(entries) for symbol, entries in resolved.items()},
        issues=tuple(issues),
    )


def i2c_signal_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _I2C_FUNCTIONS.get(compact)


def _can_function_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _CAN_FUNCTIONS.get(compact)


def usb_data_function_side(function: str) -> str | None:
    """Return the bounded USB 2.0 D+/D- side for a native pin-function alias."""
    identity = usb_data_function_identity(function)
    return identity[1] if identity is not None else None


def usb_data_function_identity(function: str) -> tuple[str | None, str] | None:
    """Return the USB data-port group and side for a bounded pin-function alias.

    Unnumbered D+/D- aliases have no port group. Numbered DPn/DMn and USBnD+/-
    aliases retain their port number so multiport hubs are not flattened into
    one ambiguous pair.
    """
    normalized = _complementary_function_key(function)
    numbered = re.fullmatch(r"(?:usb)?d([pm])([1-9][0-9]*)", normalized)
    if numbered is not None:
        return numbered.group(2), "positive" if numbered.group(1) == "p" else "negative"
    prefixed_numbered = re.fullmatch(r"usb([1-9][0-9]*)d([pm+-])", normalized)
    if prefixed_numbered is not None:
        side = "positive" if prefixed_numbered.group(2) in {"p", "+"} else "negative"
        return prefixed_numbered.group(1), side
    family_side = _COMPLEMENTARY_FUNCTIONS.get(normalized)
    if family_side is None or family_side[0] != "USB data":
        return None
    return None, family_side[1]


def complementary_signal_gaps(
    observed: NetlistContract,
    alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
) -> tuple[ComplementaryLineGap, ...]:
    """Review built-in and project-scoped complementary pairs in native netlist assignments."""
    alias_resolution = alias_resolution or ComplementaryPinFunctionAliasResolution(by_symbol={})
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    groups: dict[tuple[str, str], dict[str, list[str]]] = {}
    group_aliases: dict[tuple[str, str], ComplementaryPinFunctionAlias] = {}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        symbol = observed.component_symbols.get(reference)
        if symbol is None:
            continue
        compact = _complementary_function_key(function)
        role = _COMPLEMENTARY_FUNCTIONS.get(compact)
        alias_entry = None
        if role is None:
            for candidate in alias_resolution.by_symbol.get(symbol, ()):
                if compact in {
                    _complementary_function_key(item) for item in candidate.positive_functions
                }:
                    role = (candidate.family, "positive")
                    alias_entry = candidate
                    break
                if compact in {
                    _complementary_function_key(item) for item in candidate.negative_functions
                }:
                    role = (candidate.family, "negative")
                    alias_entry = candidate
                    break
        if role is None:
            continue
        family, side = role
        group_key = (reference, family)
        groups.setdefault(group_key, {"positive": [], "negative": []})[side].append(pin)
        if alias_entry is not None:
            group_aliases[group_key] = alias_entry

    findings: list[ComplementaryLineGap] = []
    for (reference, family), roles in sorted(groups.items()):
        pins = {side: tuple(sorted(roles[side])) for side in ("positive", "negative")}
        nets = {
            side: tuple(net for pin in pins[side] for net in sorted(pin_nets.get(pin, ())))
            for side in ("positive", "negative")
        }
        if not pins["positive"] or not pins["negative"]:
            reason = "one recognized pair side is absent from the symbol pin functions"
        elif len(pins["positive"]) != 1 or len(pins["negative"]) != 1:
            reason = "the symbol maps multiple pins to one pair side"
        elif any(len(pin_nets.get(pin, ())) != 1 for side in pins.values() for pin in side):
            reason = "one or both pair pins lack a unique schematic net assignment"
        else:
            positive_net = next(iter(pin_nets[pins["positive"][0]]))
            negative_net = next(iter(pin_nets[pins["negative"][0]]))
            if positive_net == negative_net:
                reason = "both pair functions share one schematic net"
            else:
                continue
        findings.append(
            ComplementaryLineGap(
                reference=reference,
                family=family,
                reason=reason,
                pins=pins,
                nets=nets,
                alias_symbol=(
                    group_aliases[(reference, family)].symbol
                    if (reference, family) in group_aliases
                    else None
                ),
                alias_basis=(
                    group_aliases[(reference, family)].basis
                    if (reference, family) in group_aliases
                    else None
                ),
                alias_sha256=(
                    _complementary_alias_sha256(group_aliases[(reference, family)])
                    if (reference, family) in group_aliases
                    else None
                ),
            )
        )
    return tuple(findings)


def unconnected_interface_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedInterfacePin, ...]:
    """Find unassigned pins with a narrow, recognizable interface function."""
    connected = {pin for pins in observed.nets.values() for pin in pins}
    gaps: list[UnconnectedInterfacePin] = []
    for pin, function in observed.pin_functions.items():
        if pin in connected:
            continue
        compact = re.sub(r"[^a-z0-9]", "", function.casefold())
        if i2c_signal_role(function) is not None:
            protocol: Literal["i2c", "spi", "usb_c", "can"] = "i2c"
        elif compact in _SPI_CHIP_SELECT_FUNCTIONS:
            protocol = "spi"
        elif compact in {"cc1", "cc2"}:
            protocol = "usb_c"
        elif _can_function_role(function) is not None:
            protocol = "can"
        else:
            continue
        gaps.append(UnconnectedInterfacePin(protocol=protocol, pin=pin, function=function))
    return tuple(sorted(gaps, key=lambda item: (item.protocol, item.pin, item.function)))


def is_active_low_chip_select_function(function: str) -> bool:
    """Recognize explicit active-low spelling without assuming bare CS polarity."""
    raw = function.casefold().replace("−", "-").strip()
    compact = re.sub(r"[^a-z0-9]", "", raw)
    if compact in _SPI_ACTIVE_LOW_CHIP_SELECT_FUNCTIONS:
        return True
    active_low_marked = any(marker in raw for marker in ("~", "#", "!", "/", "̅"))
    return active_low_marked and compact in {"cs", "ss", "chipselect"}


def resistance_ohms(value: str) -> float | None:
    compact = value.strip().replace("Ω", "").replace("Ω", "").casefold()
    compact = re.sub(r"ohms?$", "", compact).replace(" ", "")
    engineering = _ENGINEERING_VALUE.fullmatch(compact)
    if engineering is not None:
        amount = float(f"{engineering['whole']}.{engineering['fraction']}")
        unit = engineering["unit"]
    else:
        standard = _STANDARD_VALUE.fullmatch(compact)
        if standard is None:
            return None
        amount = float(standard["amount"])
        unit = standard["unit"]
    scale = {"": 1.0, "r": 1.0, "k": 1_000.0, "m": 1_000_000.0}[unit]
    return amount * scale


def direct_resistors(observed: NetlistContract) -> tuple[DirectResistor, ...]:
    """Return fitted, conventional two-terminal resistors with two unique net assignments."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    component_pins: dict[str, set[str]] = {}
    for pin in set(observed.pin_functions) | set(pin_nets):
        component_pins.setdefault(pin.rsplit(".", 1)[0], set()).add(pin)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    resistors: list[DirectResistor] = []
    for reference, component in observed.components.items():
        if reference.casefold() in dnp or _RESISTOR_REFERENCE.fullmatch(reference) is None:
            continue
        resistance = resistance_ohms(component.value)
        if resistance is None or resistance <= 0:
            continue
        pins = component_pins.get(reference, set())
        known_pin_numbers = observed.component_pin_numbers.get(reference)
        if len(pins) != 2 or (known_pin_numbers is not None and len(known_pin_numbers) != 2):
            continue
        terminals = [pin_nets.get(pin, set()) for pin in pins]
        if any(len(nets) != 1 for nets in terminals):
            continue
        first_net, second_net = sorted(next(iter(nets)) for nets in terminals)
        if first_net == second_net:
            continue
        resistors.append(
            DirectResistor(
                reference=reference,
                resistance_ohms=resistance,
                first_net=first_net,
                second_net=second_net,
            )
        )
    return tuple(
        sorted(resistors, key=lambda item: (item.first_net, item.second_net, item.reference))
    )


def _i2c_array_component_issues(
    array: I2cPullupArrayRequirement,
    components: dict[str, tuple[str, ComponentContract]],
    symbols: dict[str, str],
    pin_numbers: dict[str, set[str]],
    dnp: set[str],
) -> tuple[str, ...]:
    reference_key = array.reference.casefold()
    issues: list[str] = []
    component_entry = components.get(reference_key)
    if component_entry is None:
        issues.append(f"{array.reference} is absent from the native netlist")
    else:
        _, component = component_entry
        if component.footprint != array.expected_footprint:
            issues.append(
                f"{array.reference} footprint is {component.footprint or 'empty'}; "
                f"expected {array.expected_footprint}"
            )
        if component.value.strip().casefold() != array.expected_value.strip().casefold():
            issues.append(
                f"{array.reference} value is {component.value}; expected {array.expected_value}"
            )
    observed_symbol = symbols.get(reference_key)
    if observed_symbol != array.expected_symbol:
        issues.append(
            f"{array.reference} symbol is {observed_symbol or 'unknown'}; "
            f"expected {array.expected_symbol}"
        )
    if reference_key in dnp:
        issues.append(f"{array.reference} is DNP but a mapped pull-up channel is required")

    inventory = pin_numbers.get(reference_key)
    if inventory is None:
        issues.append(f"{array.reference} has no native symbol pin inventory")
    else:
        expected_numbers = {
            pin.rsplit(".", 1)[1].casefold()
            for channel in array.channels
            for pin in (channel.signal_pin, channel.rail_pin)
        }
        expected_numbers.update(
            pin.rsplit(".", 1)[1].casefold() for pin in array.unmapped_pin_reasons
        )
        missing = tuple(sorted(expected_numbers - inventory))
        unaccounted = tuple(sorted(inventory - expected_numbers))
        if missing:
            issues.append(
                f"{array.reference} mapped pins are absent from symbol inventory: {missing}"
            )
        if unaccounted:
            issues.append(
                f"{array.reference} has unreviewed symbol pins outside the array map: {unaccounted}"
            )
    return tuple(issues)


def _i2c_array_channel_issue(
    reference: str,
    channel_id: str,
    signal_pin: str,
    rail_pin: str,
    signal_net: str,
    rail_net: str,
    pin_nets: dict[str, set[str]],
) -> str | None:
    signal_assignments = pin_nets.get(signal_pin.casefold(), set())
    rail_assignments = pin_nets.get(rail_pin.casefold(), set())
    direct = signal_assignments == {signal_net} and rail_assignments == {rail_net}
    reversed_ends = signal_assignments == {rail_net} and rail_assignments == {signal_net}
    if direct or reversed_ends:
        return None
    signal_observed = ", ".join(sorted(signal_assignments)) or "unconnected"
    rail_observed = ", ".join(sorted(rail_assignments)) or "unconnected"
    return (
        f"{reference} channel {channel_id}: {signal_pin} is on {signal_observed} and "
        f"{rail_pin} is on {rail_observed}; expected one pin on {signal_net} and one on {rail_net}"
    )


def _i2c_series_path_check(
    path: I2cPullupSeriesPathRequirement,
    observed: NetlistContract,
    resistors: tuple[DirectResistor, ...],
    check_id: str,
) -> tuple[ElectricalCheck, float | None]:
    """Check one authored resistor chain and its branch-free native junctions."""
    issues: list[str] = []
    total_ohms = 0.0
    pin_for_net_by_reference: dict[str, dict[str, str]] = {}
    resistor_by_reference: dict[str, list[DirectResistor]] = {}
    for resistor in resistors:
        resistor_by_reference.setdefault(resistor.reference.casefold(), []).append(resistor)

    for requirement in path.resistors:
        reference_key = requirement.reference.casefold()
        components = [
            (reference, component)
            for reference, component in observed.components.items()
            if reference.casefold() == reference_key
        ]
        if len(components) != 1:
            issues.append(
                f"{requirement.reference} is "
                + ("absent" if not components else "ambiguous")
                + " in the native netlist"
            )
            component_reference = requirement.reference
            component = None
        else:
            component_reference, component = components[0]

        symbols = [
            symbol
            for reference, symbol in observed.component_symbols.items()
            if reference.casefold() == reference_key
        ]
        if len(symbols) != 1 or symbols[0] != requirement.expected_symbol:
            actual_symbol = symbols[0] if len(symbols) == 1 else "<unknown>"
            issues.append(
                f"{requirement.reference} symbol is {actual_symbol}; "
                f"expected {requirement.expected_symbol}"
            )
        if component is not None:
            if component.footprint != requirement.expected_footprint:
                issues.append(
                    f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                    f"expected {requirement.expected_footprint}"
                )
            if reference_key in {item.casefold() for item in observed.dnp_components}:
                issues.append(f"{requirement.reference} is DNP but the pull-up is required")

        actual_matches = resistor_by_reference.get(reference_key, [])
        if len(actual_matches) != 1:
            issues.append(
                f"{requirement.reference} is "
                + (
                    "not a recognized fitted two-terminal resistor"
                    if actual_matches
                    else "missing or not a recognized fitted two-terminal resistor"
                )
            )
        else:
            actual = actual_matches[0]
            actual_path = {actual.first_net, actual.second_net}
            if actual_path != {requirement.from_net, requirement.to_net}:
                issues.append(
                    f"{requirement.reference} connects {actual.first_net}/{actual.second_net}; "
                    f"expected {requirement.from_net}/{requirement.to_net}"
                )
            if not requirement.minimum_ohms <= actual.resistance_ohms <= requirement.maximum_ohms:
                issues.append(
                    f"{requirement.reference} is {actual.resistance_ohms:g}Ω, outside "
                    f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
                )
            total_ohms += actual.resistance_ohms

        inventories = [
            tuple(numbers)
            for reference, numbers in observed.component_pin_numbers.items()
            if reference.casefold() == reference_key
        ]
        if len(inventories) != 1:
            issues.append(
                f"{requirement.reference} native pin inventory is "
                + ("missing" if not inventories else "ambiguous")
            )
            continue
        pin_numbers = tuple(dict.fromkeys(str(number) for number in inventories[0]))
        if len(pin_numbers) != 2:
            issues.append(
                f"{requirement.reference} native pin inventory has {len(pin_numbers)} unique pins; "
                "expected exactly two"
            )
            continue

        pin_for_net: dict[str, str] = {}
        for number in pin_numbers:
            pin = f"{component_reference}.{number}"
            assigned = {
                net
                for net, pins in observed.nets.items()
                if any(candidate.casefold() == pin.casefold() for candidate in pins)
            }
            if len(assigned) != 1:
                actual_nets = ", ".join(sorted(assigned)) or "unconnected"
                issues.append(
                    f"{pin} is assigned to {actual_nets}; each series resistor pin must have one net"
                )
                continue
            net = next(iter(assigned))
            if net not in {requirement.from_net, requirement.to_net}:
                issues.append(
                    f"{pin} is assigned to {net}; expected {requirement.from_net} or "
                    f"{requirement.to_net}"
                )
            elif net in pin_for_net:
                issues.append(f"{requirement.reference} has multiple pins on {net}")
            else:
                pin_for_net[net] = pin
        if set(pin_for_net) != {requirement.from_net, requirement.to_net}:
            issues.append(
                f"{requirement.reference} does not assign exactly one native pin to each "
                f"of {requirement.from_net}/{requirement.to_net}"
            )
        pin_for_net_by_reference[reference_key] = pin_for_net

    for first, second in zip(path.resistors, path.resistors[1:], strict=False):
        junction = first.to_net
        first_pins = pin_for_net_by_reference.get(first.reference.casefold(), {})
        second_pins = pin_for_net_by_reference.get(second.reference.casefold(), {})
        expected = {first_pins.get(junction), second_pins.get(junction)}
        expected.discard(None)
        actual = {pin.casefold() for pin in observed.nets.get(junction, ())}
        expected_normalized = {pin.casefold() for pin in expected if pin is not None}
        if actual != expected_normalized:
            observed_pins = ", ".join(sorted(actual)) or "no pins"
            expected_display = (
                ", ".join(sorted(expected_normalized)) or "the two mapped resistor pins"
            )
            issues.append(
                f"series junction {junction} contains {observed_pins}; expected only "
                f"{expected_display}"
            )

    result = ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=total_ohms if not issues else None,
        unit="Ω",
        detail=(
            "; ".join(issues)
            if issues
            else f"{' + '.join(item.reference for item in path.resistors)}="
            f"{total_ohms:g}Ω forms the declared unbranched path "
            f"{path.signal_net} to {path.rail_net}."
        ),
    )
    return result, total_ohms if not issues else None


def i2c_pullup_checks(
    spec: I2cPullupAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare authored bus ranges with direct, exact series, and mapped array paths."""
    resistors = direct_resistors(observed)
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    array_component_issues = {
        array.reference.casefold(): _i2c_array_component_issues(
            array, components, symbols, pin_numbers, dnp
        )
        for array in spec.arrays
    }
    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        for name, line in (("SDA", bus.sda), ("SCL", bus.scl)):
            direct_paths = tuple(
                item
                for item in resistors
                if {item.first_net, item.second_net} == {line.net, line.rail}
            )
            mapped_channels = tuple(
                (array, channel)
                for array in spec.arrays
                for channel in array.channels
                if channel.signal_net == line.net and channel.rail_net == line.rail
            )
            array_values: list[float] = []
            array_path_names: list[str] = []
            array_failures: list[str] = []
            for array, channel in mapped_channels:
                channel_issues = list(array_component_issues[array.reference.casefold()])
                channel_issue = _i2c_array_channel_issue(
                    array.reference,
                    channel.id,
                    channel.signal_pin,
                    channel.rail_pin,
                    line.net,
                    line.rail,
                    pin_nets,
                )
                if channel_issue is not None:
                    channel_issues.append(channel_issue)
                if channel_issues:
                    array_failures.extend(channel_issues)
                else:
                    array_values.append(channel.resistance_ohms)
                    array_path_names.append(
                        f"{array.reference}.{channel.id}={channel.resistance_ohms:g}Ω"
                    )
            series_values: list[float] = []
            series_path_names: list[str] = []
            series_failures: list[str] = []
            for series_path in spec.series_paths:
                if (series_path.signal_net, series_path.rail_net) != (line.net, line.rail):
                    continue
                series_check, series_value = _i2c_series_path_check(
                    series_path,
                    observed,
                    resistors,
                    f"i2c-pullup/{bus.id}/{name.casefold()}/series/{series_path.id}",
                )
                results.append(series_check)
                if series_value is None:
                    series_failures.append(series_check.detail)
                else:
                    series_values.append(series_value)
                    series_path_names.append(
                        f"{' + '.join(item.reference for item in series_path.resistors)}="
                        f"{series_value:g}Ω"
                    )
            unexpected_rails = tuple(
                item
                for item in resistors
                if line.net in {item.first_net, item.second_net}
                and (
                    other_net := (item.second_net if item.first_net == line.net else item.first_net)
                )
                in positive_rails
                and other_net != line.rail
            )
            path_values = (
                [item.resistance_ohms for item in direct_paths] + array_values + series_values
            )
            equivalent = 1 / sum(1 / value for value in path_values) if path_values else None
            passed = (
                equivalent is not None
                and line.minimum_ohms <= equivalent <= line.maximum_ohms
                and not unexpected_rails
                and not array_failures
                and not series_failures
            )
            details = [f"{item.reference}={item.resistance_ohms:g}Ω" for item in direct_paths]
            path_summary = ", ".join((*details, *array_path_names, *series_path_names)) or (
                "no recognized fitted path"
            )
            equivalent_summary = (
                "none" if equivalent is None else f"{equivalent:g}Ω nominal parallel equivalent"
            )
            unexpected_summary = (
                ""
                if not unexpected_rails
                else "; unexpected direct pull-ups to "
                + ", ".join(
                    sorted(
                        {
                            item.second_net if item.first_net == line.net else item.first_net
                            for item in unexpected_rails
                        }
                    )
                )
            )
            array_failure_summary = (
                ""
                if not array_failures
                else "; mapped resistor-array issue: " + "; ".join(dict.fromkeys(array_failures))
            )
            series_failure_summary = (
                ""
                if not series_failures
                else "; mapped series-path issue: " + "; ".join(dict.fromkeys(series_failures))
            )
            results.append(
                ElectricalCheck(
                    id=f"i2c-pullup/{bus.id}/{name.casefold()}",
                    status="PASS" if passed else "FAIL",
                    observed=equivalent,
                    unit="Ω",
                    detail=(
                        f"{name} net {line.net} to {line.rail}: {path_summary}; "
                        f"{equivalent_summary}; required nominal range "
                        f"{line.minimum_ohms:g}–{line.maximum_ohms:g}Ω"
                        f"{unexpected_summary}{array_failure_summary}{series_failure_summary}."
                    ),
                )
            )
            results.extend(_i2c_pullup_electrical_window_checks(bus.id, name, line))
            if line.voltage_compatibility is not None:
                results.append(
                    _i2c_pullup_voltage_compatibility_check(
                        bus.id,
                        name,
                        line,
                        line.voltage_compatibility,
                        observed,
                    )
                )
    return tuple(results)


def _i2c_pullup_electrical_window_checks(
    bus_id: str, line_name: str, line: I2cPullupLineRequirement
) -> tuple[ElectricalCheck, ...]:
    window = line.electrical_window
    if window is None:
        return ()

    minimum_ohms = (
        (window.maximum_pullup_voltage_v - window.maximum_low_level_voltage_v)
        * 1_000
        / window.minimum_sink_current_ma
    )
    maximum_ohms = (
        window.maximum_rise_time_ns * 1_000 / (0.8473 * window.maximum_bus_capacitance_pf)
    )
    tolerance = window.maximum_per_resistor_tolerance_percent
    tolerance_fraction = 0.0 if tolerance is None else tolerance / 100
    minimum_actual_ohms = line.minimum_ohms * (1 - tolerance_fraction)
    maximum_actual_ohms = line.maximum_ohms * (1 + tolerance_fraction)
    feasible = minimum_ohms < maximum_ohms or math.isclose(
        minimum_ohms, maximum_ohms, rel_tol=1e-12
    )
    empty_detail = (
        " The derived resistor window is empty because its minimum exceeds its maximum."
        if not feasible
        else ""
    )
    minimum_meets_window = minimum_actual_ohms > minimum_ohms or math.isclose(
        minimum_actual_ohms, minimum_ohms, rel_tol=1e-12
    )
    maximum_meets_window = maximum_actual_ohms < maximum_ohms or math.isclose(
        maximum_actual_ohms, maximum_ohms, rel_tol=1e-12
    )
    minimum_status = "PASS" if feasible and minimum_meets_window else "FAIL"
    maximum_status = "PASS" if feasible and maximum_meets_window else "FAIL"
    prefix = f"i2c-pullup/{bus_id}/{line_name.casefold()}/electrical-window"
    minimum_note = (
        ""
        if tolerance is None
        else (
            f"; with the project-authored maximum per-resistor tolerance of {tolerance:g}% "
            f"({window.resistor_tolerance_basis}), the conservative minimum is "
            f"{minimum_actual_ohms:g}Ω"
        )
    )
    maximum_note = (
        ""
        if tolerance is None
        else (
            f"; with the project-authored maximum per-resistor tolerance of {tolerance:g}% "
            f"({window.resistor_tolerance_basis}), the conservative maximum is "
            f"{maximum_actual_ohms:g}Ω"
        )
    )
    return (
        ElectricalCheck(
            id=f"{prefix}/minimum-sink-resistance",
            status=minimum_status,
            observed=(line.minimum_ohms if tolerance is None else minimum_actual_ohms),
            unit="Ω",
            detail=(
                f"The authored {line_name} nominal resistance lower bound to {line.rail} is "
                f"{line.minimum_ohms:g}Ω{minimum_note}; the minimum derived from pull-up rail, low-level "
                f"voltage, and sink-current limits is {minimum_ohms:g}Ω "
                f"(Vpullup,max={window.maximum_pullup_voltage_v:g}V; "
                f"VOL,max={window.maximum_low_level_voltage_v:g}V; "
                f"IOL,min={window.minimum_sink_current_ma:g}mA). Sources: "
                f"{window.pullup_voltage_basis}; {window.low_level_voltage_basis}; "
                f"{window.sink_current_basis}.{empty_detail}"
            ),
        ),
        ElectricalCheck(
            id=f"{prefix}/maximum-rise-resistance",
            status=maximum_status,
            observed=(line.maximum_ohms if tolerance is None else maximum_actual_ohms),
            unit="Ω",
            detail=(
                f"The authored {line_name} nominal resistance upper bound to {line.rail} is "
                f"{line.maximum_ohms:g}Ω{maximum_note}; the maximum derived from the 30%-to-70% RC "
                f"rise-time model is {maximum_ohms:g}Ω "
                f"(tr,max={window.maximum_rise_time_ns:g}ns; "
                f"Cb,max={window.maximum_bus_capacitance_pf:g}pF; "
                "tr=0.8473×Rp×Cb). Sources: "
                f"{window.rise_time_basis}; {window.bus_capacitance_basis}."
                f"{empty_detail}"
            ),
        ),
    )


def _i2c_pullup_voltage_compatibility_check(
    bus_id: str,
    line_name: str,
    line: I2cPullupLineRequirement,
    requirement: I2cPullupVoltageCompatibilityRequirement,
    observed: NetlistContract,
) -> ElectricalCheck:
    """Compare an authored pull-up rail ceiling with exact mapped input limits."""
    components = {
        reference.casefold(): (reference, item) for reference, item in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(number.casefold() for number in numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    issues: list[str] = []

    for input_limit in requirement.input_limits:
        reference, pin_number = input_limit.pin.rsplit(".", 1)
        component = components.get(reference.casefold())
        if component is None:
            issues.append(f"{input_limit.pin} component is absent from the native netlist")
        else:
            actual_reference, details = component
            if actual_reference.casefold() in dnp:
                issues.append(f"{actual_reference} is DNP but is mapped as an active I2C input")
            actual_symbol = symbols.get(reference.casefold())
            if actual_symbol != input_limit.expected_symbol:
                issues.append(
                    f"{reference} symbol is {actual_symbol or '<unknown>'}; "
                    f"expected {input_limit.expected_symbol}"
                )
            if details.footprint != input_limit.expected_footprint:
                issues.append(
                    f"{reference} footprint is {details.footprint or '<empty>'}; "
                    f"expected {input_limit.expected_footprint}"
                )
            native_pin_numbers = inventories.get(reference.casefold())
            if native_pin_numbers is None:
                issues.append(f"{reference} native pin inventory is missing")
            elif pin_number.casefold() not in native_pin_numbers:
                issues.append(
                    f"{input_limit.pin} is absent from the native pin inventory of {reference}"
                )

        actual_nets = pin_nets.get(input_limit.pin.casefold(), set())
        if {net.casefold() for net in actual_nets} != {line.net.casefold()}:
            actual = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
            issues.append(f"{input_limit.pin} is assigned to {actual}; expected only {line.net}")
        if requirement.maximum_rail_voltage_v > input_limit.maximum_bus_voltage_v:
            issues.append(
                f"{line.rail} maximum {requirement.maximum_rail_voltage_v:g} V exceeds "
                f"{input_limit.pin} maximum bus voltage {input_limit.maximum_bus_voltage_v:g} V "
                f"({input_limit.limit_kind}; {input_limit.limit_basis})"
            )

    input_summary = "; ".join(
        f"{item.pin} <= {item.maximum_bus_voltage_v:g} V ({item.limit_kind}; {item.limit_basis})"
        for item in requirement.input_limits
    )
    authored_limits = (
        f"reviewed input scope ({requirement.input_scope_basis}); "
        f"{line.rail} maximum {requirement.maximum_rail_voltage_v:g} V "
        f"({requirement.rail_basis}); input limits: {input_summary}"
    )
    return ElectricalCheck(
        id=f"i2c-pullup/{bus_id}/{line_name.casefold()}/voltage-compatibility",
        status="FAIL" if issues else "PASS",
        observed=requirement.maximum_rail_voltage_v,
        unit="V",
        detail=(
            f"{authored_limits}; " + "; ".join(issues)
            if issues
            else (
                f"{authored_limits} is compatible on {line.net}; exact native symbol, footprint, "
                "pin inventory, and net assignments match."
            )
        ),
    )


def can_termination_checks(
    spec: CanTerminationAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare exact authored CAN termination paths with a native netlist."""
    resistors = direct_resistors(observed)
    resistors_by_reference = {item.reference.casefold(): item for item in resistors}
    components = {
        reference.casefold(): (reference, item) for reference, item in observed.components.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    component_pins: dict[str, set[str]] = {}
    for pin in set(observed.pin_functions) | set(pin_nets):
        component_pins.setdefault(pin.rsplit(".", 1)[0].casefold(), set()).add(pin)
    known_pins = set(observed.pin_functions) | set(pin_nets)
    known_pins.update(
        f"{reference}.{number}"
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    )

    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        pin_failures: list[str] = []
        for label, required_net, pins in (
            ("CANH", bus.high_net, bus.high_pins),
            ("CANL", bus.low_net, bus.low_pins),
        ):
            for pin in pins:
                if pin not in known_pins:
                    pin_failures.append(
                        f"{label} pin {pin} is absent from the native symbol pin inventory"
                    )
                    continue
                assigned = pin_nets.get(pin, set())
                if assigned != {required_net}:
                    nets = ", ".join(sorted(assigned)) if assigned else "unconnected"
                    pin_failures.append(
                        f"{label} pin {pin} is assigned to {nets}; expected {required_net}"
                    )
        results.append(
            ElectricalCheck(
                id=f"can-termination/{bus.id}/signal-pins",
                status="FAIL" if pin_failures else "PASS",
                detail=(
                    "; ".join(pin_failures)
                    if pin_failures
                    else f"Declared CANH/CANL pins are assigned to {bus.high_net}/{bus.low_net}."
                ),
            )
        )
        expected_direct = {
            resistor.reference.casefold()
            for endpoint in bus.endpoints
            if endpoint.topology == "direct"
            for resistor in endpoint.resistors
        }
        actual_direct = tuple(
            item
            for item in resistors
            if {item.first_net, item.second_net} == {bus.high_net, bus.low_net}
        )
        unlisted_direct = tuple(
            item for item in actual_direct if item.reference.casefold() not in expected_direct
        )
        results.append(
            ElectricalCheck(
                id=f"can-termination/{bus.id}/unlisted-direct",
                status="FAIL" if unlisted_direct else "PASS",
                detail=(
                    "Unlisted direct resistors across the declared CAN nets: "
                    + ", ".join(
                        f"{item.reference}={item.resistance_ohms:g}Ω" for item in unlisted_direct
                    )
                    if unlisted_direct
                    else f"No unlisted direct resistor across {bus.high_net} and {bus.low_net}."
                ),
            )
        )
        for endpoint in bus.endpoints:
            base_id = f"can-termination/{bus.id}/{endpoint.id}"
            if endpoint.topology == "external":
                results.append(
                    ElectricalCheck(
                        id=f"{base_id}/external-evidence",
                        status="NOT_APPLICABLE",
                        detail=(
                            f"External termination is explicitly declared for endpoint {endpoint.id}: "
                            f"{endpoint.basis}. A schematic netlist cannot verify remote hardware."
                        ),
                    )
                )
                if endpoint.expected_dnp_resistors:
                    failures: list[str] = []
                    for reference in endpoint.expected_dnp_resistors:
                        key = reference.casefold()
                        component_entry = components.get(key)
                        if component_entry is None:
                            failures.append(f"{reference} is absent from the netlist")
                            continue
                        _, component = component_entry
                        if key not in dnp:
                            failures.append(f"{reference} is fitted, expected DNP")
                        if _RESISTOR_REFERENCE.fullmatch(reference) is None:
                            failures.append(f"{reference} is not a recognized resistor reference")
                        value = resistance_ohms(component.value)
                        if value is None or value <= 0:
                            failures.append(
                                f"{reference} has no recognized positive resistor value"
                            )
                        pins = component_pins.get(key, set())
                        assigned_nets = [pin_nets.get(pin, set()) for pin in pins]
                        known_pin_numbers = observed.component_pin_numbers.get(component_entry[0])
                        if (
                            len(pins) != 2
                            or (known_pin_numbers is not None and len(known_pin_numbers) != 2)
                            or any(len(nets) != 1 for nets in assigned_nets)
                            or {next(iter(nets)) for nets in assigned_nets if len(nets) == 1}
                            != {bus.high_net, bus.low_net}
                        ):
                            failures.append(
                                f"{reference} does not map exactly across {bus.high_net}/{bus.low_net}"
                            )
                    results.append(
                        ElectricalCheck(
                            id=f"{base_id}/dnp-options",
                            status="FAIL" if failures else "PASS",
                            detail=(
                                "; ".join(failures)
                                if failures
                                else "Expected DNP termination option(s) are present across the declared CAN nets: "
                                + ", ".join(endpoint.expected_dnp_resistors)
                                + "."
                            ),
                        )
                    )
                continue

            path_details: list[str] = []
            failures = []
            observed_total = 0.0
            for requirement in endpoint.resistors:
                resistor = resistors_by_reference.get(requirement.reference.casefold())
                if resistor is None:
                    if requirement.reference.casefold() in dnp:
                        failures.append(f"{requirement.reference} is DNP but must be fitted")
                    elif requirement.reference.casefold() not in components:
                        failures.append(f"{requirement.reference} is absent from the netlist")
                    else:
                        failures.append(
                            f"{requirement.reference} is not a recognized fitted two-terminal resistor"
                        )
                    continue
                observed_total += resistor.resistance_ohms
                actual_path = {resistor.first_net, resistor.second_net}
                expected_path = {requirement.first_net, requirement.second_net}
                if actual_path != expected_path:
                    failures.append(
                        f"{requirement.reference} connects {resistor.first_net}/{resistor.second_net}, "
                        f"expected {requirement.first_net}/{requirement.second_net}"
                    )
                if (
                    not requirement.minimum_ohms
                    <= resistor.resistance_ohms
                    <= requirement.maximum_ohms
                ):
                    failures.append(
                        f"{requirement.reference} is {resistor.resistance_ohms:g}Ω, outside "
                        f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
                    )
                path_details.append(
                    f"{resistor.reference}={resistor.resistance_ohms:g}Ω "
                    f"({requirement.first_net}/{requirement.second_net})"
                )
            results.append(
                ElectricalCheck(
                    id=base_id,
                    status="FAIL" if failures else "PASS",
                    observed=observed_total
                    if len(path_details) == len(endpoint.resistors)
                    else None,
                    unit="Ω",
                    detail=(
                        f"{endpoint.topology} termination at {endpoint.id} on "
                        f"{bus.high_net}/{bus.low_net}: "
                        + ("; ".join(failures) if failures else ", ".join(path_details))
                        + "."
                    ),
                )
            )
            if endpoint.midpoint_capacitor is not None:
                assert endpoint.midpoint_net is not None
                results.append(
                    _can_midpoint_capacitor_check(
                        endpoint.midpoint_capacitor,
                        endpoint.midpoint_net,
                        observed,
                        f"{base_id}/midpoint-capacitor",
                    )
                )
    return tuple(results)


def _can_midpoint_capacitor_check(
    requirement: CanTerminationMidpointCapacitorRequirement,
    midpoint_net: str,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Check one explicitly mapped capacitor and its exact two native pin nets."""
    issues: list[str] = []
    reference_key = requirement.reference.casefold()
    component_matches = [
        (reference, component)
        for reference, component in observed.components.items()
        if reference.casefold() == reference_key
    ]
    if len(component_matches) != 1:
        issues.append(
            f"{requirement.reference} is "
            + ("absent" if not component_matches else "ambiguous")
            + " in the native netlist"
        )
        component = None
    else:
        _, component = component_matches[0]

    symbols = [
        symbol
        for reference, symbol in observed.component_symbols.items()
        if reference.casefold() == reference_key
    ]
    if len(symbols) != 1 or symbols[0] != requirement.expected_symbol:
        actual = symbols[0] if len(symbols) == 1 else "<unknown>"
        issues.append(
            f"{requirement.reference} symbol is {actual}; expected {requirement.expected_symbol}"
        )

    if component is not None:
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {requirement.expected_footprint}"
            )
        if reference_key in {item.casefold() for item in observed.dnp_components}:
            issues.append(f"{requirement.reference} is DNP but must be fitted")
        capacitance_pf = parse_capacitance_pf(component.value)
        if capacitance_pf is None:
            issues.append(f"{requirement.reference} has no recognized positive capacitance value")
        elif not (
            requirement.minimum_nominal_capacitance_pf
            <= capacitance_pf
            <= requirement.maximum_nominal_capacitance_pf
        ):
            issues.append(
                f"{requirement.reference} is {capacitance_pf:g}pF, outside "
                f"{requirement.minimum_nominal_capacitance_pf:g}–"
                f"{requirement.maximum_nominal_capacitance_pf:g}pF"
            )
    else:
        capacitance_pf = None

    inventory_matches = [
        numbers
        for reference, numbers in observed.component_pin_numbers.items()
        if reference.casefold() == reference_key
    ]
    expected_pins = {requirement.midpoint_pin.casefold(), requirement.reference_pin.casefold()}
    if len(inventory_matches) != 1:
        issues.append(
            f"{requirement.reference} native pin inventory is "
            + ("missing" if not inventory_matches else "ambiguous")
        )
    else:
        pin_numbers = {str(number).casefold() for number in inventory_matches[0]}
        expected_numbers = {
            requirement.midpoint_pin.rsplit(".", 1)[1].casefold(),
            requirement.reference_pin.rsplit(".", 1)[1].casefold(),
        }
        if len(pin_numbers) != 2 or pin_numbers != expected_numbers:
            issues.append(
                f"{requirement.reference} native pin inventory is "
                f"{', '.join(sorted(pin_numbers)) or '<empty>'}; expected exactly "
                f"{', '.join(sorted(expected_numbers))}"
            )

    native_pins = {
        pin.casefold()
        for pin in set(observed.pin_functions)
        | {pin for pins in observed.nets.values() for pin in pins}
        if pin.rsplit(".", 1)[0].casefold() == reference_key
    }
    extra_pins = native_pins - expected_pins
    if extra_pins:
        issues.append(
            f"{requirement.reference} has unexpected mapped pins: " + ", ".join(sorted(extra_pins))
        )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    for pin, expected_net in (
        (requirement.midpoint_pin, midpoint_net),
        (requirement.reference_pin, requirement.reference_net),
    ):
        assigned = pin_nets.get(pin.casefold(), set())
        if assigned != {expected_net}:
            actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
            issues.append(f"{pin} is assigned to {actual}; expected only {expected_net}")

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=None if capacitance_pf is None else float(capacitance_pf),
        unit="pF",
        detail=(
            "; ".join(issues)
            if issues
            else f"{requirement.reference}={capacitance_pf:g}pF maps "
            f"{requirement.midpoint_pin} to {midpoint_net} and "
            f"{requirement.reference_pin} to {requirement.reference_net}."
        ),
    )


def _usb_c_vbus_path_check(
    requirement: UsbCVbusPathRequirement,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Compare one authored component and net chain with the native pin inventory."""
    issues: list[str] = []
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    for pin, expected_net in (
        (requirement.connector_pin, requirement.connector_net),
        (requirement.board_pin, requirement.board_net),
    ):
        assigned = pin_nets.get(pin.casefold(), set())
        if assigned != {expected_net}:
            actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
            issues.append(f"{pin} is assigned to {actual}; expected only {expected_net}")

    for element in requirement.elements:
        key = element.reference.casefold()
        component_matches = [
            (reference, component)
            for reference, component in observed.components.items()
            if reference.casefold() == key
        ]
        if len(component_matches) != 1:
            issues.append(
                f"{element.reference} is "
                + ("absent" if not component_matches else "ambiguous")
                + " in the native netlist"
            )
            continue

        reference, component = component_matches[0]
        if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
            issues.append(f"{reference} is DNP but the VBUS path requires it fitted")
        symbol_matches = [
            symbol
            for symbol_reference, symbol in observed.component_symbols.items()
            if symbol_reference.casefold() == key
        ]
        if len(symbol_matches) != 1 or symbol_matches[0] != element.symbol:
            actual = symbol_matches[0] if len(symbol_matches) == 1 else "<unknown>"
            issues.append(f"{reference} symbol is {actual}; expected {element.symbol}")
        if component.footprint != element.footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {element.footprint}"
            )

        inventory_matches = [
            numbers
            for inventory_reference, numbers in observed.component_pin_numbers.items()
            if inventory_reference.casefold() == key
        ]
        if len(inventory_matches) != 1:
            issues.append(
                f"{reference} native pin inventory is "
                + ("missing" if not inventory_matches else "ambiguous")
            )
        else:
            known_numbers = {str(number).casefold() for number in inventory_matches[0]}
            expected_numbers = {
                assignment.pin.rsplit(".", 1)[1].casefold()
                for assignment in element.pin_assignments
            }
            missing_numbers = expected_numbers - known_numbers
            if missing_numbers:
                issues.append(
                    f"{reference} native pin inventory omits mapped pin(s): "
                    + ", ".join(sorted(missing_numbers))
                )

        for assignment in element.pin_assignments:
            assigned = pin_nets.get(assignment.pin.casefold(), set())
            if assigned != {assignment.net}:
                actual = ", ".join(sorted(assigned)) if assigned else "unconnected"
                issues.append(
                    f"{assignment.pin} is assigned to {actual}; expected only {assignment.net}"
                )

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        detail=(
            "; ".join(issues)
            if issues
            else (
                f"The authored connector-to-board VBUS map contains "
                f"{len(requirement.elements)} exact component boundary/boundaries and matches "
                "the native symbol, footprint, pin inventory, and pin-to-net evidence."
            )
        ),
    )


def usb_c_vbus_capacitance_check(
    requirement: UsbCVbusCapacitanceRequirement,
    *,
    vbus_net: str,
    ground_net: str,
    observed: NetlistContract,
    check_id: str,
) -> ElectricalCheck:
    """Compare mapped nominal port-side capacitance with project-authored limits."""
    issues: list[str] = []
    expected_nets = {vbus_net.casefold(), ground_net.casefold()}
    if len(expected_nets) != 2:
        return ElectricalCheck(
            id=check_id,
            status="FAIL",
            detail="The authored VBUS and ground nets are not distinct.",
        )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    mapped_references = {item.reference.casefold() for item in requirement.capacitors}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    component_index: dict[str, list[tuple[str, ComponentContract]]] = {}
    for reference, component in observed.components.items():
        component_index.setdefault(reference.casefold(), []).append((reference, component))
    symbol_index: dict[str, list[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        symbol_index.setdefault(reference.casefold(), []).append(symbol)
    inventory_index: dict[str, list[tuple[str, ...]]] = {}
    for reference, numbers in observed.component_pin_numbers.items():
        inventory_index.setdefault(reference.casefold(), []).append(
            tuple(str(number) for number in numbers)
        )

    total_pf = Decimal(0)
    complete_values = True
    for capacitor in requirement.capacitors:
        key = capacitor.reference.casefold()
        matches = component_index.get(key, [])
        if len(matches) != 1:
            issues.append(
                f"{capacitor.reference} is "
                + ("absent" if not matches else "ambiguous")
                + " in the native netlist"
            )
            complete_values = False
            continue
        reference, component = matches[0]
        if key in dnp:
            issues.append(f"{reference} is DNP but the VBUS capacitance map requires it fitted")

        symbols = symbol_index.get(key, [])
        if len(symbols) != 1 or symbols[0] != capacitor.symbol:
            actual = symbols[0] if len(symbols) == 1 else "<unknown>"
            issues.append(f"{reference} symbol is {actual}; expected {capacitor.symbol}")
        if component.footprint != capacitor.footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {capacitor.footprint}"
            )

        inventories = inventory_index.get(key, [])
        expected_pins = {item.pin.rsplit(".", 1)[1].casefold() for item in capacitor.pins}
        if len(inventories) != 1:
            issues.append(
                f"{reference} native pin inventory is "
                + ("missing" if not inventories else "ambiguous")
            )
        else:
            actual_pins = {number.casefold() for number in inventories[0]}
            if actual_pins != expected_pins:
                issues.append(
                    f"{reference} native pin inventory is {sorted(actual_pins)}; "
                    f"expected {sorted(expected_pins)}"
                )

        assigned_nets: set[str] = set()
        for assignment in capacitor.pins:
            expected_net = assignment.net.casefold()
            if expected_net not in expected_nets:
                issues.append(
                    f"{assignment.pin} maps to {assignment.net}; expected the port VBUS or ground net"
                )
            actual = pin_nets.get(assignment.pin.casefold(), set())
            if actual != {assignment.net}:
                rendered = ", ".join(sorted(actual)) if actual else "unconnected"
                issues.append(
                    f"{assignment.pin} is assigned to {rendered}; expected only {assignment.net}"
                )
            assigned_nets.update(net.casefold() for net in actual)
        if assigned_nets != expected_nets:
            issues.append(f"{reference} does not span exactly {vbus_net} and {ground_net}")

        capacitance_pf = parse_capacitance_pf(component.value)
        if capacitance_pf is None:
            issues.append(f"{reference} value {component.value!r} is not a supported capacitance")
            complete_values = False
        else:
            total_pf += capacitance_pf

    for key, matches in sorted(component_index.items()):
        if key in mapped_references or key in dnp or len(matches) != 1:
            continue
        reference, _component = matches[0]
        symbols = symbol_index.get(key, [])
        symbol_suggests_capacitor = len(symbols) == 1 and (
            "capacitor" in symbols[0].rsplit(":", 1)[-1].casefold()
            or symbols[0].rsplit(":", 1)[-1].casefold() in {"c", "cp"}
            or symbols[0].rsplit(":", 1)[-1].casefold().startswith(("c_", "cp_"))
        )
        reference_suggests_capacitor = key.startswith(("c", "cp"))
        if not (symbol_suggests_capacitor or reference_suggests_capacitor):
            continue
        inventories = inventory_index.get(key, [])
        relevant_assigned_pins = [
            pin
            for pin, nets in pin_nets.items()
            if pin.rsplit(".", 1)[0] == key
            and any(net.casefold() == vbus_net.casefold() for net in nets)
        ]
        if not relevant_assigned_pins:
            continue
        if len(inventories) != 1:
            issues.append(
                f"Unmapped capacitor candidate {reference} touches the port VBUS net "
                "but its native pin inventory is unavailable"
            )
            continue
        if len(inventories[0]) != 2:
            issues.append(
                f"Unmapped capacitor candidate {reference} touches the port VBUS net "
                "but is not a two-pin component"
            )
            continue
        issues.append(
            f"Unmapped capacitor candidate {reference} touches the port VBUS net; "
            "include it in the reviewed capacitance inventory"
        )

    total_nf = total_pf / Decimal(1000)
    minimum_nf = Decimal(str(requirement.minimum_nf))
    maximum_nf = Decimal(str(requirement.maximum_nf))
    total_text = format(total_nf.normalize(), "f")
    minimum_text = format(minimum_nf.normalize(), "f")
    maximum_text = format(maximum_nf.normalize(), "f")
    if complete_values and not minimum_nf <= total_nf <= maximum_nf:
        issues.append(
            f"Mapped nominal total is {total_text} nF; expected {minimum_text}–{maximum_text} nF"
        )

    return ElectricalCheck(
        id=check_id,
        status="FAIL" if issues else "PASS",
        observed=float(total_nf) if complete_values else None,
        unit="nF",
        detail=(
            "; ".join(issues)
            if issues
            else (
                f"Mapped nominal total {total_text} nF is within the "
                f"project-authored {minimum_text}–{maximum_text} nF range "
                f"({requirement.basis})."
            )
        ),
    )


def usb_c_checks(spec: UsbCAnalysis, observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    """Compare authored USB-C CC, connector pin, component, and protection facts."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    known_pins = set(observed.pin_functions) | set(pin_nets)
    known_pins.update(
        f"{reference}.{number}"
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    )
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    resistors = direct_resistors(observed)
    resistors_by_reference = {item.reference.casefold(): item for item in resistors}

    def assignment_failure(pin: str, expected_net: str) -> str | None:
        if pin not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(pin, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    results: list[ElectricalCheck] = []
    for port in spec.ports:
        base = f"usb-c/{port.id}"
        failures = [
            issue
            for pin, net in (
                (port.cc1.connector_pin, port.cc1.net),
                (port.cc2.connector_pin, port.cc2.net),
                *((assignment.pin, assignment.net) for assignment in port.vbus_pins),
                *((pin, port.ground_net) for pin in port.ground_pins),
            )
            if (issue := assignment_failure(pin, net)) is not None
        ]
        results.append(
            ElectricalCheck(
                id=f"{base}/connector-pins",
                status="FAIL" if failures else "PASS",
                detail=(
                    "; ".join(failures)
                    if failures
                    else "Declared CC, VBUS, and ground connector/board pins match their exact nets."
                ),
            )
        )
        if port.vbus_path is not None:
            results.append(
                _usb_c_vbus_path_check(
                    port.vbus_path,
                    observed,
                    f"{base}/vbus-path/{port.vbus_path.id}",
                )
            )
        if isinstance(port.vbus_capacitance, UsbCVbusCapacitanceRequirement):
            results.append(
                usb_c_vbus_capacitance_check(
                    port.vbus_capacitance,
                    vbus_net=port.vbus_net,
                    ground_net=port.ground_net,
                    observed=observed,
                    check_id=f"{base}/vbus-capacitance",
                )
            )
        elif isinstance(port.vbus_capacitance, AnalysisPending):
            results.append(
                ElectricalCheck(
                    id=f"{base}/vbus-capacitance",
                    status="NOT_CONFIGURED",
                    detail=port.vbus_capacitance.reason,
                )
            )
        else:
            results.append(
                ElectricalCheck(
                    id=f"{base}/vbus-capacitance",
                    status="NOT_APPLICABLE",
                    detail=port.vbus_capacitance.reason,
                )
            )

        if port.controller is not None:
            entry = components.get(port.controller.reference.casefold())
            identity_failures: list[str] = []
            if entry is None:
                identity_failures.append(f"{port.controller.reference} is absent from the netlist")
            else:
                reference, component = entry
                if symbols.get(reference.casefold()) != port.controller.symbol:
                    identity_failures.append(
                        f"{reference} symbol is {symbols.get(reference.casefold(), 'unknown')}; "
                        f"expected {port.controller.symbol}"
                    )
                if component.footprint != port.controller.footprint:
                    identity_failures.append(
                        f"{reference} footprint is {component.footprint or 'empty'}; "
                        f"expected {port.controller.footprint}"
                    )
            results.append(
                ElectricalCheck(
                    id=f"{base}/controller-identity",
                    status="FAIL" if identity_failures else "PASS",
                    detail=(
                        "; ".join(identity_failures)
                        if identity_failures
                        else f"{port.controller.reference} matches the declared USB-C controller symbol and footprint."
                    ),
                )
            )

        for label, line in (("cc1", port.cc1), ("cc2", port.cc2)):
            attachment = line.attachment
            if isinstance(attachment, UsbCcResistorAttachment):
                expected_ref = attachment.reference.casefold()
                resistor = resistors_by_reference.get(expected_ref)
                entry = components.get(expected_ref)
                failures: list[str] = []
                if entry is None:
                    failures.append(f"{attachment.reference} is absent from the netlist")
                elif expected_ref in dnp:
                    failures.append(f"{attachment.reference} is DNP but must be fitted")
                if resistor is None:
                    if entry is not None and expected_ref not in dnp:
                        failures.append(
                            f"{attachment.reference} is not a recognized fitted two-terminal resistor"
                        )
                else:
                    actual_path = {resistor.first_net, resistor.second_net}
                    expected_path = {line.net, attachment.rail_net}
                    if actual_path != expected_path:
                        failures.append(
                            f"{attachment.reference} connects {resistor.first_net}/{resistor.second_net}; "
                            f"expected {line.net}/{attachment.rail_net}"
                        )
                    if (
                        not attachment.minimum_ohms
                        <= resistor.resistance_ohms
                        <= attachment.maximum_ohms
                    ):
                        failures.append(
                            f"{attachment.reference} is {resistor.resistance_ohms:g}Ω, outside "
                            f"{attachment.minimum_ohms:g}–{attachment.maximum_ohms:g}Ω"
                        )
                extras = tuple(
                    item
                    for item in resistors
                    if line.net in {item.first_net, item.second_net}
                    and item.reference.casefold() != expected_ref
                )
                if extras:
                    failures.append(
                        "unlisted fitted resistors touch this CC net: "
                        + ", ".join(item.reference for item in extras)
                    )
                detail = (
                    "; ".join(failures)
                    if failures
                    else (
                        f"{attachment.behavior.upper()} {attachment.reference}="
                        f"{resistor.resistance_ohms:g}Ω connects {line.net} to "
                        f"{attachment.rail_net} within the declared nominal range."
                    )
                    if resistor is not None
                    else f"{attachment.reference} has no recognized fitted resistor."
                )
                results.append(
                    ElectricalCheck(
                        id=f"{base}/{label}-attachment",
                        status="FAIL" if failures else "PASS",
                        observed=resistor.resistance_ohms if resistor is not None else None,
                        unit="Ω",
                        detail=detail,
                    )
                )
            else:
                failures: list[str] = []
                if (issue := assignment_failure(attachment.controller_pin, line.net)) is not None:
                    failures.append(issue)
                extras = tuple(
                    item for item in resistors if line.net in {item.first_net, item.second_net}
                )
                if extras:
                    failures.append(
                        "unlisted fitted resistors touch this controller-driven CC net: "
                        + ", ".join(item.reference for item in extras)
                    )
                results.append(
                    ElectricalCheck(
                        id=f"{base}/{label}-attachment",
                        status="FAIL" if failures else "PASS",
                        detail=(
                            "; ".join(failures)
                            if failures
                            else f"Controller pin {attachment.controller_pin} is assigned to {line.net}."
                        ),
                    )
                )

        if isinstance(port.protection, UsbCProtectionAnalysis):
            for requirement in port.protection.components:
                entry = components.get(requirement.reference.casefold())
                component_failures: list[str] = []
                if entry is None:
                    component_failures.append(f"{requirement.reference} is absent from the netlist")
                else:
                    reference, component = entry
                    if reference.casefold() in dnp:
                        component_failures.append(f"{reference} is DNP but protection is required")
                    if symbols.get(reference.casefold()) != requirement.symbol:
                        component_failures.append(
                            f"{reference} symbol is {symbols.get(reference.casefold(), 'unknown')}; "
                            f"expected {requirement.symbol}"
                        )
                    if component.footprint != requirement.footprint:
                        component_failures.append(
                            f"{reference} footprint is {component.footprint or 'empty'}; "
                            f"expected {requirement.footprint}"
                        )
                for assignment in requirement.pins:
                    if (issue := assignment_failure(assignment.pin, assignment.net)) is not None:
                        component_failures.append(issue)
                results.append(
                    ElectricalCheck(
                        id=f"{base}/protection/{requirement.reference}",
                        status="FAIL" if component_failures else "PASS",
                        detail=(
                            "; ".join(component_failures)
                            if component_failures
                            else f"{requirement.reference} matches the declared symbol, footprint, and pin nets."
                        ),
                    )
                )
        elif isinstance(port.protection, AnalysisPending):
            results.append(
                ElectricalCheck(
                    id=f"{base}/protection",
                    status="NOT_CONFIGURED",
                    detail=port.protection.reason,
                )
            )
        else:
            results.append(
                ElectricalCheck(
                    id=f"{base}/protection",
                    status="NOT_APPLICABLE",
                    detail=port.protection.reason,
                )
            )

        if port.role == "debug_accessory":
            results.append(
                ElectricalCheck(
                    id=f"{base}/role-support",
                    status="NOT_RUN",
                    detail="USB-C debug-accessory role behavior is not modeled by this deterministic v1 check.",
                )
            )
    return tuple(results)


def _positive_power_nets(observed: NetlistContract) -> set[str]:
    """Return only the positive rails identified by a bounded native name/function map."""
    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    return positive_rails


def _positive_power_net_families(observed: NetlistContract) -> dict[str, str]:
    """Return recognized positive nets with one stable, narrow naming family."""
    families: dict[str, str] = {}
    for net, pins in observed.nets.items():
        family = power_function_key(net)
        if family is None:
            pin_families = {
                key
                for pin in pins
                if (key := power_function_key(observed.pin_functions.get(pin, ""))) is not None
            }
            if len(pin_families) == 1:
                family = next(iter(pin_families))
        if family is not None:
            families[net] = family
    return families


def _visible_resistor_pullups(observed: NetlistContract) -> dict[str, list[VisiblePullupPath]]:
    """Find direct or unbranched fitted resistor chains from a signal net to a named rail."""
    positive_rails = _positive_power_nets(observed)
    resistors = {
        item.reference: item
        for item in direct_resistors(observed)
        if 1_000 <= item.resistance_ohms <= 100_000
    }
    by_net: dict[str, list[DirectResistor]] = {}
    for resistor in resistors.values():
        by_net.setdefault(resistor.first_net, []).append(resistor)
        by_net.setdefault(resistor.second_net, []).append(resistor)

    pullups: dict[str, dict[tuple[tuple[str, ...], str], VisiblePullupPath]] = {}

    def visit(
        start_net: str,
        current_net: str,
        references: tuple[str, ...],
        resistance_ohms: float,
        visited: frozenset[str],
    ) -> None:
        for resistor in by_net.get(current_net, ()):
            if resistor.reference in visited:
                continue
            next_net = (
                resistor.second_net if resistor.first_net == current_net else resistor.first_net
            )
            path_references = (*references, resistor.reference)
            path_resistance = resistance_ohms + resistor.resistance_ohms
            if next_net in positive_rails:
                if 1_000 <= path_resistance <= 100_000:
                    path = VisiblePullupPath(
                        references=path_references,
                        resistance_ohms=path_resistance,
                        rail_net=next_net,
                    )
                    pullups.setdefault(start_net, {})[(path_references, next_net)] = path
                continue
            if next_net == start_net:
                continue

            # Only traverse a series junction with exactly two assigned pins,
            # both belonging to recognized fitted two-terminal resistors.
            junction_pins = tuple(observed.nets.get(next_net, ()))
            if len(junction_pins) != 2 or len(set(junction_pins)) != 2:
                continue
            junction_references = {pin.rsplit(".", 1)[0] for pin in junction_pins}
            if len(junction_references) != 2 or resistor.reference not in junction_references:
                continue
            next_references = junction_references - {resistor.reference}
            if len(next_references) != 1:
                continue
            next_reference = next(iter(next_references))
            next_resistor = resistors.get(next_reference)
            if next_resistor is None or next_net not in {
                next_resistor.first_net,
                next_resistor.second_net,
            }:
                continue
            visit(
                start_net,
                next_net,
                path_references,
                path_resistance,
                visited | {resistor.reference},
            )

    for start_net in sorted(by_net):
        if start_net in positive_rails:
            continue
        visit(start_net, start_net, (), 0.0, frozenset())

    return {
        net: sorted(
            paths.values(),
            key=lambda item: (item.rail_net, item.references, item.resistance_ohms),
        )
        for net, paths in sorted(pullups.items())
    }


def spi_active_low_chip_selects_without_pullups(
    observed: NetlistContract,
) -> tuple[SpiChipSelectBiasGap, ...]:
    """Find assigned active-low SPI input pins without a visible local pull-up path."""
    positive_rails = _positive_power_nets(observed)
    if not positive_rails:
        return ()

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    chip_selects_by_net: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() in dnp or not is_active_low_chip_select_function(function):
            continue
        if observed.pin_electrical_types.get(pin, "").casefold() not in {"input", "input_low"}:
            continue
        assignments = pin_nets.get(pin, set())
        if len(assignments) != 1:
            continue
        net = next(iter(assignments))
        if net in positive_rails or is_return_like_net_name(net):
            continue
        chip_selects_by_net.setdefault(net, set()).add(pin)

    visible_pullups = _visible_resistor_pullups(observed)
    return tuple(
        SpiChipSelectBiasGap(
            net=net,
            pins=tuple(sorted(pins)),
            positive_rails=tuple(sorted(positive_rails)),
        )
        for net, pins in sorted(chip_selects_by_net.items())
        if net not in visible_pullups
    )


def i2c_buses_without_local_pullups(observed: NetlistContract) -> tuple[I2cPullupGap, ...]:
    """Find named SDA/SCL pairs without a 1 kΩ–100 kΩ path to a named rail."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    pullup_nets = set(_visible_resistor_pullups(observed))

    gaps: list[I2cPullupGap] = []
    for (sda_net, scl_net), evidence in sorted(buses.items()):
        missing_lines: list[Literal["SDA", "SCL"]] = []
        if sda_net not in pullup_nets:
            missing_lines.append("SDA")
        if scl_net not in pullup_nets:
            missing_lines.append("SCL")
        missing = tuple(missing_lines)
        if missing:
            gaps.append(
                I2cPullupGap(
                    sda_net=sda_net,
                    scl_net=scl_net,
                    sda_pins=tuple(sorted(evidence["SDA"])),
                    scl_pins=tuple(sorted(evidence["SCL"])),
                    missing_lines=missing,
                )
            )
    return tuple(gaps)


def i2c_pullup_heuristic_coverage(
    observed: NetlistContract,
    *,
    netlist_sha256: str,
    source_path: str | None,
    source_sha256: str | None,
    state: str,
    spec: I2cPullupAnalysis | None = None,
) -> I2cPullupHeuristicCoverage:
    """Resolve only exact missing-line hints with passing authored pull-up checks."""
    gaps = i2c_buses_without_local_pullups(observed)
    if spec is None:
        reason = {
            "pending": "Project I2C pull-up review is pending; no requirement can resolve this prompt.",
            "not_applicable": "The project marks I2C pull-up analysis not applicable; no net-specific requirement resolves this prompt.",
            "blocked": "The project I2C pull-up requirement could not be loaded.",
        }.get(state, "No project-authored I2C pull-up requirement covers this candidate.")
        entries: list[I2cPullupHeuristicEntry] = [
            I2cPullupHeuristicEntry(
                sda_net=gap.sda_net,
                scl_net=gap.scl_net,
                missing_lines=gap.missing_lines,
                status="OPEN",
                issues=(reason,),
            )
            for gap in gaps
        ]
        status_by_state: dict[
            str,
            Literal["NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"],
        ] = {
            "pending": "PENDING",
            "not_applicable": "NOT_APPLICABLE",
            "blocked": "BLOCKED",
        }
        status = status_by_state.get(state, "NOT_CONFIGURED")
        return I2cPullupHeuristicCoverage(
            status=status,
            source_path=source_path,
            source_sha256=source_sha256,
            netlist_sha256=netlist_sha256 if gaps else None,
            entries=tuple(entries),
            issue=(reason if state == "blocked" else None),
        )

    checks_by_id = {check.id: check for check in i2c_pullup_checks(spec, observed)}
    entries: list[I2cPullupHeuristicEntry] = []
    for gap in gaps:
        matching = [
            bus
            for bus in spec.buses
            if bus.sda.net.casefold() == gap.sda_net.casefold()
            and bus.scl.net.casefold() == gap.scl_net.casefold()
        ]
        if len(matching) != 1:
            issue = (
                "No I2C pull-up requirement names this exact ordered SDA/SCL net pair."
                if not matching
                else "More than one I2C pull-up requirement names this exact ordered SDA/SCL net pair."
            )
            entries.append(
                I2cPullupHeuristicEntry(
                    sda_net=gap.sda_net,
                    scl_net=gap.scl_net,
                    missing_lines=gap.missing_lines,
                    status="OPEN",
                    issues=(issue,),
                )
            )
            continue

        bus = matching[0]
        required_check_ids: list[str] = []
        issues: list[str] = []
        lines: dict[str, I2cPullupLineRequirement] = {"SDA": bus.sda, "SCL": bus.scl}
        for line_name in ("SDA", "SCL"):
            line = lines[line_name]
            check_id = f"i2c-pullup/{bus.id}/{line_name.casefold()}"
            required_check_ids.append(check_id)
            check = checks_by_id.get(check_id)
            if check is None:
                issues.append(f"{line_name}: the authored pull-up check did not produce evidence.")
            elif check.status != "PASS":
                issues.append(f"{line_name}: {check.detail}")

            if line.voltage_compatibility is not None:
                voltage_id = f"{check_id}/voltage-compatibility"
                required_check_ids.append(voltage_id)
                voltage_check = checks_by_id.get(voltage_id)
                if voltage_check is None:
                    issues.append(
                        f"{line_name}: the authored voltage-compatibility check did not produce evidence."
                    )
                elif voltage_check.status != "PASS":
                    issues.append(f"{line_name} voltage compatibility: {voltage_check.detail}")

        entries.append(
            I2cPullupHeuristicEntry(
                sda_net=gap.sda_net,
                scl_net=gap.scl_net,
                missing_lines=gap.missing_lines,
                status="OPEN" if issues else "COVERED",
                bus_id=bus.id,
                check_ids=tuple(required_check_ids),
                issues=tuple(issues),
            )
        )

    coverage_status = "OPEN" if any(entry.status == "OPEN" for entry in entries) else "COMPLETE"
    return I2cPullupHeuristicCoverage(
        status=coverage_status,
        source_path=source_path,
        source_sha256=source_sha256,
        netlist_sha256=netlist_sha256 if gaps else None,
        entries=tuple(entries),
    )


def i2c_buses_with_low_equivalent_pullup_resistance(
    observed: NetlistContract,
) -> tuple[I2cLowEquivalentResistance, ...]:
    """Find direct fitted pull-ups whose nominal parallel resistance is below 1 kΩ."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    visible_pullups = _visible_resistor_pullups(observed)
    findings: list[I2cLowEquivalentResistance] = []
    for (sda_net, scl_net), evidence in sorted(buses.items()):
        affected: list[str] = []
        resistors: dict[str, tuple[str, ...]] = {}
        equivalents: dict[str, str] = {}
        for line, net in (("SDA", sda_net), ("SCL", scl_net)):
            paths = tuple(
                sorted(
                    visible_pullups.get(net, ()), key=lambda item: (item.rail_net, item.references)
                )
            )
            if not paths or len({item.rail_net for item in paths}) != 1:
                continue
            equivalent = 1 / sum(1 / item.resistance_ohms for item in paths)
            if equivalent >= 1_000:
                continue
            affected.append(line)
            equivalents[line] = f"{equivalent:.6g}"
            resistors[line] = tuple(
                f"{' + '.join(item.references)}={item.resistance_ohms:.6g}Ω to {item.rail_net}"
                for item in paths
            )
        if affected:
            findings.append(
                I2cLowEquivalentResistance(
                    sda_net=sda_net,
                    scl_net=scl_net,
                    lines=tuple(affected),
                    pins={line: tuple(sorted(evidence[line])) for line in ("SDA", "SCL")},
                    resistors=resistors,
                    equivalent_ohms=equivalents,
                )
            )
    return tuple(findings)


def i2c_buses_with_multiple_pullup_rail_families(
    observed: NetlistContract,
) -> tuple[I2cMultiplePullupRailFamilies, ...]:
    """Review an I2C bus whose visible pull-ups use distinct recognized rail families."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        if pin.rsplit(".", 1)[0].casefold() in dnp:
            continue
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    visible_pullups = _visible_resistor_pullups(observed)
    rail_families_by_net = _positive_power_net_families(observed)
    findings: list[I2cMultiplePullupRailFamilies] = []
    for (sda_net, scl_net), bus_pins in sorted(buses.items()):
        families: set[str] = set()
        paths: set[str] = set()
        for line, net in (("SDA", sda_net), ("SCL", scl_net)):
            for path in visible_pullups.get(net, ()):
                family = rail_families_by_net.get(path.rail_net)
                if family is None:
                    continue
                families.add(family)
                references = " + ".join(path.references)
                paths.add(
                    f"{line}: {references}={path.resistance_ohms:g}Ω to {path.rail_net} ({family})"
                )
        if len(families) < 2:
            continue
        findings.append(
            I2cMultiplePullupRailFamilies(
                sda_net=sda_net,
                scl_net=scl_net,
                pins=tuple(sorted((*bus_pins["SDA"], *bus_pins["SCL"]))),
                rail_families=tuple(sorted(families)),
                pullup_paths=tuple(sorted(paths)),
            )
        )
    return tuple(findings)


def can_buses_without_local_termination(
    observed: NetlistContract,
) -> tuple[CanTerminationGap, ...]:
    """Find named CANH/CANL pairs without a visible direct 108–132 Ω resistor."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = _can_function_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"CANH", "CANL"}.issubset(roles):
            continue
        high_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["CANH"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        low_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["CANL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for high_pin, high_net in high_assignments:
            for low_pin, low_net in low_assignments:
                if high_net == low_net:
                    continue
                evidence = buses.setdefault((high_net, low_net), {"CANH": set(), "CANL": set()})
                evidence["CANH"].add(high_pin)
                evidence["CANL"].add(low_pin)

    terminated_pairs: set[tuple[str, str]] = set()
    for resistor in direct_resistors(observed):
        if 108 <= resistor.resistance_ohms <= 132:
            terminated_pairs.add((resistor.first_net, resistor.second_net))

    gaps: list[CanTerminationGap] = []
    for (high_net, low_net), evidence in sorted(buses.items()):
        if tuple(sorted((high_net, low_net))) in terminated_pairs:
            continue
        gaps.append(
            CanTerminationGap(
                high_net=high_net,
                low_net=low_net,
                high_pins=tuple(sorted(evidence["CANH"])),
                low_pins=tuple(sorted(evidence["CANL"])),
            )
        )
    return tuple(gaps)


def can_peer_assignment_divergences(
    observed: NetlistContract,
) -> tuple[CanPeerAssignmentDivergence, ...]:
    """Review complete CAN pin pairs that share only one exact native net.

    Pin-function names and native assignments identify candidates; they do not
    establish that the components belong to one bus or that all peers must
    share both nets. DNP, incomplete, multi-pin-per-role, and same-net pairs
    are left to other rules or skipped as ambiguous.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    symbols_by_reference = {
        reference.casefold(): reference for reference in observed.component_symbols
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    role_pins: dict[str, dict[str, list[str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp:
            continue
        if reference.casefold() not in symbols_by_reference:
            continue
        role = _can_function_role(function)
        if role is not None:
            role_pins.setdefault(reference.casefold(), {}).setdefault(role, []).append(pin)

    participants: list[tuple[str, str, str, str, str]] = []
    for reference_key, roles in sorted(role_pins.items()):
        if len(roles.get("CANH", ())) != 1 or len(roles.get("CANL", ())) != 1:
            continue
        high_pin = roles["CANH"][0]
        low_pin = roles["CANL"][0]
        high_nets = nets_by_pin.get(high_pin.casefold(), set())
        low_nets = nets_by_pin.get(low_pin.casefold(), set())
        if len(high_nets) != 1 or len(low_nets) != 1:
            continue
        high_net = next(iter(high_nets))
        low_net = next(iter(low_nets))
        if high_net == low_net:
            continue
        participants.append(
            (
                symbols_by_reference[reference_key],
                high_pin,
                high_net,
                low_pin,
                low_net,
            )
        )

    groups: dict[tuple[str, str], list[tuple[str, str, str, str, str]]] = {}
    for participant in participants:
        _reference, high_pin, high_net, low_pin, low_net = participant
        groups.setdefault(("CANH", high_net), []).append(participant)
        groups.setdefault(("CANL", low_net), []).append(participant)

    divergences: list[CanPeerAssignmentDivergence] = []
    for (shared_role, shared_net), peers in sorted(groups.items()):
        if len(peers) < 2:
            continue
        complementary_role: Literal["CANH", "CANL"] = "CANL" if shared_role == "CANH" else "CANH"
        complementary_nets = tuple(
            sorted({peer[4] if complementary_role == "CANL" else peer[2] for peer in peers})
        )
        if len(complementary_nets) < 2:
            continue
        participant_evidence = tuple(
            sorted(
                f"{reference}:{high_pin}=CANH/{high_net};{low_pin}=CANL/{low_net}"
                for reference, high_pin, high_net, low_pin, low_net in peers
            )
        )
        divergences.append(
            CanPeerAssignmentDivergence(
                shared_role=shared_role,  # type: ignore[arg-type]
                shared_net=shared_net,
                complementary_role=complementary_role,
                complementary_nets=complementary_nets,
                participants=participant_evidence,
            )
        )
    return tuple(divergences)


def spi_checks(spec: SpiAnalysis, observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    """Compare authored SPI roles and membership with exact native pin/net evidence."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    def pin_issue(pin: str, expected_net: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    def unconnected_issue(pin: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual:
            return f"{pin} is assigned to {', '.join(sorted(actual))}; expected unconnected"
        return None

    def identity_issues(reference: str, symbol: str, footprint: str) -> list[str]:
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {symbol}"
            )
        if component.footprint != footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {footprint}"
            )
        return issues

    def pin_disposition(
        pin: SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
    ) -> str | None:
        if isinstance(pin, SpiPinUnconnectedRequirement):
            return unconnected_issue(pin.pin)
        return pin_issue(pin.pin, pin.net)

    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        base = f"spi/{bus.id}"
        controller = bus.controller
        controller_identity = identity_issues(
            controller.reference, controller.symbol, controller.footprint
        )
        results.append(
            ElectricalCheck(
                id=f"{base}/controller-identity",
                status="FAIL" if controller_identity else "PASS",
                detail=(
                    "; ".join(controller_identity)
                    if controller_identity
                    else f"{controller.reference} matches the declared SPI controller symbol and footprint."
                ),
            )
        )

        controller_pin_requirements: list[
            tuple[
                str,
                SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ]
        ] = [("SCK", controller.sck), ("MOSI", controller.mosi)]
        controller_pin_requirements.extend(
            (f"CS[{index}]", pin) for index, pin in enumerate(controller.chip_selects, start=1)
        )
        controller_pin_issues = [
            f"{role}: {issue}"
            for role, pin in controller_pin_requirements
            if (issue := pin_disposition(pin)) is not None
        ]
        if isinstance(
            controller.miso, (SpiMisoConnectedRequirement, SpiPinUnconnectedRequirement)
        ) and (issue := pin_disposition(controller.miso)):
            controller_pin_issues.append(f"MISO: {issue}")
        results.append(
            ElectricalCheck(
                id=f"{base}/controller-pins",
                status="FAIL" if controller_pin_issues else "PASS",
                detail=(
                    "; ".join(controller_pin_issues)
                    if controller_pin_issues
                    else f"Declared SCK, MOSI, MISO disposition, and {len(controller.chip_selects)} chip-select pin assignments match."
                ),
            )
        )
        if isinstance(controller.miso, SpiPinNotPresent):
            results.append(
                ElectricalCheck(
                    id=f"{base}/controller-miso",
                    status="NOT_APPLICABLE",
                    detail=f"Controller MISO is declared absent: {controller.miso.reason}",
                )
            )

        bridge_path_ok: dict[tuple[str, str, str], bool] = {}
        for bridge in bus.bridges:
            bridge_key = bridge.reference.casefold()
            issues = identity_issues(bridge.reference, bridge.symbol, bridge.footprint)
            results.append(
                ElectricalCheck(
                    id=f"{base}/bridge/{bridge.reference}/identity",
                    status="FAIL" if issues else "PASS",
                    detail=(
                        "; ".join(issues)
                        if issues
                        else f"{bridge.reference} matches the declared SPI bridge symbol and footprint."
                    ),
                )
            )
            path_issues: list[str] = []
            for path in bridge.paths:
                first = pin_issue(path.from_pin, path.from_net)
                second = pin_issue(path.to_pin, path.to_net)
                bridge_path_ok[(bridge_key, path.signal, path.from_net + "\0" + path.to_net)] = (
                    not issues and first is None and second is None
                )
                if first is not None:
                    path_issues.append(f"{path.signal} input: {first}")
                if second is not None:
                    path_issues.append(f"{path.signal} output: {second}")
            results.append(
                ElectricalCheck(
                    id=f"{base}/bridge/{bridge.reference}/pins",
                    status="FAIL" if path_issues else "PASS",
                    detail=(
                        "; ".join(path_issues)
                        if path_issues
                        else f"All {len(bridge.paths)} declared bridge path pin assignments match their nets. Internal bridge behavior is not verified."
                    ),
                )
            )

        def has_observed_route(
            signal: str,
            source: str,
            destination: str,
            *,
            bridges: tuple[SpiBridgeRequirement, ...] = bus.bridges,
            valid_paths: dict[tuple[str, str, str], bool] = bridge_path_ok,
        ) -> bool:
            if source == destination:
                return True
            graph: dict[str, set[str]] = {}
            for bridge in bridges:
                bridge_key = bridge.reference.casefold()
                for path in bridge.paths:
                    if path.signal != signal:
                        continue
                    edge_key = (bridge_key, path.signal, path.from_net + "\0" + path.to_net)
                    if not valid_paths.get(edge_key, False):
                        continue
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
            pending = [source]
            reached: set[str] = set()
            while pending:
                net = pending.pop()
                if net == destination:
                    return True
                if net in reached:
                    continue
                reached.add(net)
                pending.extend(graph.get(net, ()))
            return False

        def add_route(
            device_id: str,
            signal: str,
            source: str,
            destination: str,
            *,
            route_base: str = base,
        ) -> None:
            passed = has_observed_route(signal, source, destination)
            results.append(
                ElectricalCheck(
                    id=f"{route_base}/device/{device_id}/route/{signal}",
                    status="PASS" if passed else "FAIL",
                    detail=(
                        f"Declared {signal.upper()} route {source} to {destination} has matching endpoint assignments. Internal bridge behavior is not verified."
                        if passed
                        else f"No declared {signal.upper()} route with matching bridge pin assignments connects {source} to {destination}."
                    ),
                )
            )

        for device in bus.devices:
            device_base = f"{base}/device/{device.id}"
            issues = identity_issues(device.reference, device.symbol, device.footprint)
            results.append(
                ElectricalCheck(
                    id=f"{device_base}/identity",
                    status="FAIL" if issues else "PASS",
                    detail=(
                        "; ".join(issues)
                        if issues
                        else f"{device.reference} matches the declared SPI device symbol and footprint."
                    ),
                )
            )
            device_pin_requirements = (
                ("SCK", device.sck),
                ("MOSI", device.mosi),
                ("CS", device.chip_select),
            )
            device_pin_issues = [
                f"{role}: {issue}"
                for role, pin in device_pin_requirements
                if (issue := pin_disposition(pin)) is not None
            ]
            if isinstance(
                device.miso, (SpiMisoConnectedRequirement, SpiPinUnconnectedRequirement)
            ) and (issue := pin_disposition(device.miso)):
                device_pin_issues.append(f"MISO: {issue}")
            results.append(
                ElectricalCheck(
                    id=f"{device_base}/pins",
                    status="FAIL" if device_pin_issues else "PASS",
                    detail=(
                        "; ".join(device_pin_issues)
                        if device_pin_issues
                        else "Declared SCK, MOSI, MISO disposition, and chip-select pin assignments match."
                    ),
                )
            )
            add_route(device.id, "sck", controller.sck.net, device.sck.net)
            add_route(device.id, "mosi", controller.mosi.net, device.mosi.net)
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                if isinstance(controller.miso, SpiMisoConnectedRequirement):
                    add_route(device.id, "miso", controller.miso.net, device.miso.net)
            else:
                reason = (
                    device.miso.reason
                    if isinstance(device.miso, SpiPinNotPresent)
                    else "Device MISO is declared unconnected."
                )
                results.append(
                    ElectricalCheck(
                        id=f"{device_base}/route/miso",
                        status="NOT_APPLICABLE",
                        detail=f"No device MISO return route is required: {reason}",
                    )
                )
    return tuple(results)
