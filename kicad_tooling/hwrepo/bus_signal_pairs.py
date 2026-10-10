"""Bus signal pairs for deterministic KiCad bus analysis."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .models import (
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    NetlistContract,
)

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
