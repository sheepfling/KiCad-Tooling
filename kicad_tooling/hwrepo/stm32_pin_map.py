"""Deterministic comparison of reviewed STM32 package pins across KiCad and CubeMX."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from .models import (
    ComponentContract,
    NetlistContract,
    Stm32CubeMxPinMap,
    Stm32PinMapMismatch,
    Stm32UnmappedDevice,
)

_IOC_ASSIGNMENT = re.compile(r"^(P[A-Z][0-9]+)(?:[A-Z0-9_/-]|\\ )*\.(Signal|GPIO_Label)$")
_MAX_IOC_BYTES = 8 * 1024 * 1024
_MAX_IOC_LINES = 100_000
_Value = TypeVar("_Value")


@dataclass(frozen=True)
class CubeMxPin:
    """Selected function fields for one physical package port pin."""

    port_pin: str
    raw_key: str
    signal: str | None
    gpio_label: str | None


@dataclass(frozen=True)
class CubeMxDocument:
    """Parsed pin-related CubeMX settings and explicit input-format issues."""

    pins: dict[str, CubeMxPin]
    issues: tuple[str, ...]


def stm32_pin_map_sha256(pin_maps: Sequence[Stm32CubeMxPinMap]) -> str:
    """Fingerprint a stable, ID-sorted collection of project-authored pin maps."""
    payload = [item.model_dump(mode="json") for item in sorted(pin_maps, key=lambda item: item.id)]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_cubemx_ioc(content: bytes) -> CubeMxDocument:
    """Parse only documented pin Signal/GPIO_Label assignments without lossy overwrite."""
    if len(content) > _MAX_IOC_BYTES:
        raise ValueError(f"CubeMX IOC exceeds the {_MAX_IOC_BYTES}-byte parser limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CubeMX IOC must be UTF-8 text") from exc
    lines = text.splitlines()
    if len(lines) > _MAX_IOC_LINES:
        raise ValueError(f"CubeMX IOC exceeds the {_MAX_IOC_LINES}-line parser limit")

    fields: dict[str, dict[str, str]] = {}
    raw_keys: dict[str, tuple[str, str]] = {}
    issues: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            if line.endswith((".Signal", ".GPIO_Label")):
                issues.append(f"line {line_number}: incomplete CubeMX pin assignment {line!r}")
            continue
        key, value = line.split("=", 1)
        if not key.endswith((".Signal", ".GPIO_Label")):
            continue
        match = _IOC_ASSIGNMENT.fullmatch(key)
        if match is None:
            issues.append(f"line {line_number}: unsupported CubeMX pin key {key!r}")
            continue
        if value != value.strip():
            issues.append(f"line {line_number}: CubeMX pin value has surrounding whitespace")
            continue
        if match.group(2) == "Signal" and not value:
            issues.append(f"line {line_number}: CubeMX signal for {key!r} is empty")
            continue

        port_pin, field = match.groups()
        raw_pin_key = key.rsplit(".", 1)[0]
        normalized = port_pin.casefold()
        previous_key = raw_keys.get(normalized)
        if previous_key is not None and previous_key[1] != raw_pin_key:
            issues.append(
                f"line {line_number}: CubeMX keys {previous_key[1]!r} and {raw_pin_key!r} "
                f"both identify {port_pin}"
            )
            continue
        raw_keys[normalized] = (port_pin, raw_pin_key)
        pin_fields = fields.setdefault(normalized, {})
        if field in pin_fields:
            issues.append(
                f"line {line_number}: duplicate CubeMX {field} assignment for {raw_pin_key}"
            )
            continue
        pin_fields[field] = value

    pins = {
        key: CubeMxPin(
            port_pin=raw_keys[key][0],
            raw_key=raw_keys[key][1],
            signal=pin_fields.get("Signal"),
            gpio_label=(pin_fields.get("GPIO_Label") or None),
        )
        for key, pin_fields in fields.items()
    }
    return CubeMxDocument(pins=pins, issues=tuple(issues))


def stm32_pin_map_mismatches(
    pin_map: Stm32CubeMxPinMap,
    observed: NetlistContract,
    document: CubeMxDocument,
    *,
    ioc_sha256: str,
    map_sha256: str,
    netlist_sha256: str,
) -> tuple[Stm32PinMapMismatch, ...]:
    """Compare authored package mapping against exact component, net and IOC observations."""
    mismatches: list[Stm32PinMapMismatch] = []
    component = _lookup(observed.components, pin_map.reference)
    observed_symbol = _lookup(observed.component_symbols, pin_map.reference)
    observed_numbers = _lookup(observed.component_pin_numbers, pin_map.reference)
    component_dnp = pin_map.reference.casefold() in {
        reference.casefold() for reference in observed.dnp_components
    }

    for requirement in pin_map.pins:
        issues: list[str] = []
        if not isinstance(component, ComponentContract):
            issues.append(f"{pin_map.reference} is absent or ambiguous in the native netlist")
        else:
            if component.value != pin_map.expected_part:
                issues.append(
                    f"{pin_map.reference} part is {component.value}; expected {pin_map.expected_part}"
                )
        if observed_symbol != pin_map.expected_symbol:
            issues.append(
                f"{pin_map.reference} symbol is {observed_symbol or 'unknown'}; "
                f"expected {pin_map.expected_symbol}"
            )
        if component_dnp:
            issues.append(f"{pin_map.reference} is marked DNP but has an active CubeMX map")
        if observed_numbers is None:
            issues.append(f"{pin_map.reference} native pin inventory is unavailable")
        elif requirement.symbol_pin.casefold() not in {
            str(number).casefold() for number in observed_numbers
        }:
            issues.append(
                f"{pin_map.reference}.{requirement.symbol_pin} is absent from the native pin inventory"
            )

        pin_reference = f"{pin_map.reference}.{requirement.symbol_pin}"
        observed_nets = tuple(
            sorted(
                net
                for net, pins in observed.nets.items()
                if any(pin.casefold() == pin_reference.casefold() for pin in pins)
            )
        )
        if observed_nets != (requirement.expected_net,):
            issues.append(
                f"{pin_reference} is on {', '.join(observed_nets) or 'unconnected'}; "
                f"expected {requirement.expected_net}"
            )

        ioc_pin = document.pins.get(requirement.port_pin.casefold())
        observed_signal = None if ioc_pin is None else ioc_pin.signal
        observed_gpio_label = None if ioc_pin is None else ioc_pin.gpio_label
        if ioc_pin is None:
            issues.append(f"CubeMX IOC has no assignment for {requirement.port_pin}")
        elif observed_signal not in requirement.accepted_ioc_signals:
            issues.append(
                f"CubeMX {requirement.port_pin} signal is {observed_signal or 'missing'}; "
                f"expected one of {', '.join(requirement.accepted_ioc_signals)}"
            )
        if (
            ioc_pin is not None
            and requirement.accepted_ioc_gpio_labels is not None
            and observed_gpio_label not in requirement.accepted_ioc_gpio_labels
        ):
            expected_labels = tuple(
                "<absent>" if label is None else label
                for label in requirement.accepted_ioc_gpio_labels
            )
            issues.append(
                f"CubeMX {requirement.port_pin} GPIO label is "
                f"{observed_gpio_label or '<absent>'}; expected one of {', '.join(expected_labels)}"
            )

        if issues:
            mismatches.append(
                Stm32PinMapMismatch(
                    map_id=pin_map.id,
                    reference=pin_map.reference,
                    port_pin=requirement.port_pin,
                    symbol_pin=requirement.symbol_pin,
                    expected_net=requirement.expected_net,
                    observed_nets=observed_nets,
                    accepted_ioc_signals=requirement.accepted_ioc_signals,
                    observed_ioc_signal=observed_signal,
                    accepted_ioc_gpio_labels=requirement.accepted_ioc_gpio_labels,
                    observed_ioc_gpio_label=observed_gpio_label,
                    ioc_path=pin_map.ioc_path,
                    ioc_sha256=ioc_sha256,
                    map_sha256=map_sha256,
                    netlist_sha256=netlist_sha256,
                    issues=tuple(issues),
                )
            )
    return tuple(mismatches)


def unmapped_stm32_devices(
    observed: NetlistContract,
    mapped_references: tuple[str, ...],
    *,
    netlist_sha256: str,
) -> tuple[Stm32UnmappedDevice, ...]:
    """Prompt for likely fitted STM32 components lacking any CubeMX pin-map contract."""
    mapped = {reference.casefold() for reference in mapped_references}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    results: list[Stm32UnmappedDevice] = []
    for reference, component in observed.components.items():
        if reference.casefold() in mapped or reference.casefold() in dnp:
            continue
        symbol = _lookup(observed.component_symbols, reference)
        if "stm32" not in f"{component.value} {symbol or ''}".casefold():
            continue
        results.append(
            Stm32UnmappedDevice(
                reference=reference,
                observed_symbol=symbol,
                observed_part=component.value,
                netlist_sha256=netlist_sha256,
            )
        )
    return tuple(sorted(results, key=lambda item: item.reference.casefold()))


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None
