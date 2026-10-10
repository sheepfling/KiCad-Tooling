"""Shared connector identity and pin-role interpretation rules."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .models import ConnectorMappedPinEvidence, NetlistContract, SimilarConnectorPinGroup

_CONNECTOR_REFERENCE = re.compile(r"^(?:J|P|X|CN)[0-9]+$", re.IGNORECASE)


_GENERIC_PIN_FUNCTION = re.compile(r"^pin[_\s]*[0-9]+$", re.IGNORECASE)


_RETURN_FUNCTIONS = frozenset(
    {
        "0v",
        "gnd",
        "gnda",
        "gndd",
        "gndp",
        "ground",
        "agnd",
        "dgnd",
        "pgnd",
        "analogground",
        "digitalground",
        "powerground",
        "signalgnd",
        "signalground",
        "vss",
        "vssa",
        "vssd",
        "vssp",
        "rtn",
        "return",
    }
)


_SHIELD_FUNCTIONS = frozenset({"shield", "chassis", "earth", "frame", "fg"})


_POWER_FUNCTIONS = {
    "pwr": "pwr",
    "power": "pwr",
    "vin": "vin",
    "vcc": "vcc",
    "vdd": "vdd",
    "vbus": "vbus",
    "supply": "supply",
    "vsupply": "supply",
    "vccio": "vccio",
    "vddio": "vddio",
    "5v": "5v",
    "3v3": "3v3",
    "3.3v": "3v3",
    "1v8": "1v8",
    "1.8v": "1v8",
    "2v5": "2v5",
    "2.5v": "2v5",
    "12v": "12v",
    "24v": "24v",
}


def power_function_key(function: str) -> str | None:
    """Return a narrow supply-pin category, preserving rail identity."""
    compact = re.sub(r"[\s_/]+", "", function).casefold()
    if compact.startswith("-"):
        return None
    compact = compact.removeprefix("+")
    return _POWER_FUNCTIONS.get(compact)


def is_named_supply_function(function: str) -> bool:
    compact = re.sub(r"[\s_/]+", "", function).casefold()
    compact = compact.removeprefix("+").removeprefix("-")
    return compact in _POWER_FUNCTIONS


def is_return_function(function: str) -> bool:
    compact = re.sub(r"[\s_./-]+", "", function).casefold()
    return re.sub(r"\d+$", "", compact) in _RETURN_FUNCTIONS


def is_shield_function(function: str) -> bool:
    compact = re.sub(r"[\s_./-]+", "", function).casefold()
    return re.sub(r"\d+$", "", compact) in _SHIELD_FUNCTIONS


def has_meaningful_pin_function(function: str | None) -> bool:
    """Treat absent roles and KiCad's generic Pin_N labels as unknown metadata."""
    return function is not None and _GENERIC_PIN_FUNCTION.fullmatch(function.strip()) is None


def pin_function_is_generic(function: str | None) -> bool:
    """Return whether native pin metadata does not identify an electrical role."""
    return (
        function is None
        or not function.strip()
        or _GENERIC_PIN_FUNCTION.fullmatch(function.strip()) is not None
        or re.fullmatch(r"[0-9]+", function.strip()) is not None
    )


def _function_group(function: str, symbol: str) -> tuple[str, str] | None:
    """Compare named roles, excluding generic Pin_N placeholders."""
    if not has_meaningful_pin_function(function):
        return None
    if is_return_function(function):
        return "<connector-return>", "ground/return"
    power_key = power_function_key(function)
    if power_key is not None:
        return "<connector-power>", power_key
    return symbol.casefold(), function.casefold()


def connector_candidate_references(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    include_exact_symbol_peers: bool = False,
) -> tuple[str, ...]:
    """Return bounded connector candidates from native or project-authored identity.

    Designator prefixes and standard Connector libraries provide automatic
    candidate evidence. A project-owned interface review may additionally
    classify an exact custom symbol/reference pair; that classification does
    not establish its pinout or electrical requirements. Callers may also
    include every instance of an exact symbol used by a declared connector, so
    an omitted peer remains a coverage candidate.
    """
    symbols_by_reference = {
        reference.casefold(): reference for reference in observed.component_symbols
    }
    declared = {
        symbols_by_reference[reference.casefold()]
        for reference in declared_references
        if reference.casefold() in symbols_by_reference
    }
    exact_symbol_peers: set[str] = set()
    if include_exact_symbol_peers:
        declared_symbols = {
            observed.component_symbols[reference].casefold()
            for reference in declared
            if reference in observed.component_symbols
        }
        exact_symbol_peers = {
            reference
            for reference, symbol_id in observed.component_symbols.items()
            if symbol_id.casefold() in declared_symbols
        }
    return tuple(
        sorted(
            declared
            | exact_symbol_peers
            | {
                reference
                for reference, symbol_id in observed.component_symbols.items()
                if _CONNECTOR_REFERENCE.fullmatch(reference) is not None
                or _is_standard_connector_symbol(symbol_id)
            },
            key=lambda item: (item.casefold(), item),
        )
    )


def _is_standard_connector_symbol(symbol_id: str) -> bool:
    """Recognize standard connector-library identities, excluding Connector test points."""
    library, separator, symbol = symbol_id.partition(":")
    if not separator:
        return False
    normalized_library = library.casefold()
    if normalized_library != "connector" and not normalized_library.startswith("connector_"):
        return False
    normalized_symbol = re.sub(r"[^a-z0-9]+", "", symbol.casefold())
    return not (normalized_library == "connector" and normalized_symbol.startswith("testpoint"))


def similar_connector_pin_groups(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
    *,
    include_consistent: bool = False,
) -> tuple[SimilarConnectorPinGroup, ...]:
    """Find repeated connector roles on differing or missing nets, without judging intent.

    ``include_consistent`` retains same-net groups for source-bound coverage
    reporting; normal lint candidates include only differing or open groups.
    """
    reviewed_connector_pins = reviewed_connector_pins or {}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    grouped: dict[tuple[str, str], list[tuple[str, str, str, tuple[str, ...]]]] = {}
    for pin in sorted(set(observed.pin_functions) | set(reviewed_connector_pins)):
        function = observed.pin_functions.get(pin)
        ref = pin.rsplit(".", 1)[0]
        if ref.casefold() not in connector_references or ref.casefold() in unpopulated:
            continue
        symbol = observed.component_symbols.get(ref)
        if symbol is None:
            continue
        mapped = reviewed_connector_pins.get(pin)
        if mapped is not None and mapped.role == "return" and pin_function_is_generic(function):
            key = ("<connector-return>", "ground/return")
        elif (
            mapped is not None
            and mapped.role == "supply"
            and mapped.voltage_domain is not None
            and pin_function_is_generic(function)
        ):
            key = ("<connector-mapped-supply>", mapped.voltage_domain)
        elif function is None:
            key = None
        else:
            key = _function_group(function, symbol)
        if key is None:
            continue
        grouped.setdefault(key, []).append(
            (pin, symbol, function or "", tuple(sorted(pin_nets.get(pin, ()))))
        )
    result: list[SimilarConnectorPinGroup] = []
    for key, entries in sorted(grouped.items()):
        is_role_group = key[0] in {
            "<connector-return>",
            "<connector-power>",
            "<connector-mapped-supply>",
        }
        assignments = {pin: nets for pin, _, _, nets in entries}
        for peer_group, scoped, peer_review in partition_peer_assignments(
            assignments,
            None if is_role_group else peer_assignment_groups,
        ):
            scoped_entries = [entry for entry in entries if entry[0] in scoped]
            connector_refs = {pin.rsplit(".", 1)[0] for pin, _, _, _ in scoped_entries}
            if len(scoped_entries) < 2 or (not is_role_group and len(connector_refs) < 2):
                continue
            if (
                not include_consistent
                and len({nets for _, _, _, nets in scoped_entries}) == 1
                and scoped_entries[0][3]
            ):
                continue
            scoped_entries.sort()
            symbols = {symbol.casefold() for _, symbol, _, _ in scoped_entries}
            mapped_supply = key[0] == "<connector-mapped-supply>"
            result.append(
                SimilarConnectorPinGroup(
                    symbol=(
                        scoped_entries[0][1] if len(symbols) == 1 else "multiple connector symbols"
                    ),
                    function=(
                        "ground/return"
                        if key[0] == "<connector-return>"
                        else f"supply in voltage domain {key[1]}"
                        if mapped_supply
                        else scoped_entries[0][2]
                    ),
                    pins={pin: nets for pin, _, _, nets in scoped_entries},
                    reviewed_role="supply" if mapped_supply else None,
                    reviewed_voltage_domain=key[1] if mapped_supply else None,
                    peer_assignment_group=peer_group,
                    peer_assignment_basis=peer_review,
                )
            )
    return tuple(result)


def partition_peer_assignments(
    assignments: Mapping[str, tuple[str, ...]],
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None,
) -> tuple[tuple[str | None, dict[str, tuple[str, ...]], tuple[str, ...]], ...]:
    """Scope a comparison only when every participating connector has a current group."""
    if not peer_assignment_groups:
        return ((None, dict(assignments), ()),)
    groups = {
        reference.casefold(): (group, basis)
        for reference, (group, basis) in peer_assignment_groups.items()
    }
    connector_references = tuple(
        sorted(
            {pin.rsplit(".", 1)[0] for pin in assignments},
            key=lambda item: (item.casefold(), item),
        )
    )
    if not connector_references or any(
        reference.casefold() not in groups for reference in connector_references
    ):
        return ((None, dict(assignments), ()),)

    partitions: dict[str, tuple[str, dict[str, tuple[str, ...]], set[str]]] = {}
    for pin, nets in sorted(assignments.items(), key=lambda item: (item[0].casefold(), item[0])):
        reference = pin.rsplit(".", 1)[0]
        group, basis = groups[reference.casefold()]
        group_key = group.casefold()
        if group_key not in partitions:
            partitions[group_key] = (group, {}, set())
        display_group, scoped_assignments, review_evidence = partitions[group_key]
        scoped_assignments[pin] = nets
        review_evidence.add(f"{reference}: {display_group}; {basis}")
    return tuple(
        (
            display_group,
            scoped_assignments,
            tuple(sorted(review_evidence, key=lambda item: (item.casefold(), item))),
        )
        for _, (display_group, scoped_assignments, review_evidence) in sorted(partitions.items())
    )
