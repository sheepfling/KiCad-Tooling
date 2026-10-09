"""Review hints for connector pin, supply, and return patterns in a native netlist."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .models import (
    ConnectorMappedPinEvidence,
    ConnectorPeerPinHeuristicCoverage,
    NetlistContract,
    SimilarConnectorPinGroup,
)

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


def _is_named_supply_function(function: str) -> bool:
    compact = re.sub(r"[\s_/]+", "", function).casefold()
    compact = compact.removeprefix("+").removeprefix("-")
    return compact in _POWER_FUNCTIONS


def _is_return_function(function: str) -> bool:
    compact = re.sub(r"[\s_./-]+", "", function).casefold()
    return re.sub(r"\d+$", "", compact) in _RETURN_FUNCTIONS


def _is_shield_function(function: str) -> bool:
    compact = re.sub(r"[\s_./-]+", "", function).casefold()
    return re.sub(r"\d+$", "", compact) in _SHIELD_FUNCTIONS


def _has_meaningful_pin_function(function: str | None) -> bool:
    """Treat absent roles and KiCad's generic Pin_N labels as unknown metadata."""
    return function is not None and _GENERIC_PIN_FUNCTION.fullmatch(function.strip()) is None


def _pin_function_is_generic(function: str | None) -> bool:
    """Return whether native pin metadata does not identify an electrical role."""
    return (
        function is None
        or not function.strip()
        or _GENERIC_PIN_FUNCTION.fullmatch(function.strip()) is not None
        or re.fullmatch(r"[0-9]+", function.strip()) is not None
    )


def _function_group(function: str, symbol: str) -> tuple[str, str] | None:
    """Compare named roles, excluding generic Pin_N placeholders."""
    if not _has_meaningful_pin_function(function):
        return None
    if _is_return_function(function):
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
        if mapped is not None and mapped.role == "return" and _pin_function_is_generic(function):
            key = ("<connector-return>", "ground/return")
        elif (
            mapped is not None
            and mapped.role == "supply"
            and mapped.voltage_domain is not None
            and _pin_function_is_generic(function)
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
        for peer_group, scoped, peer_review in _peer_assignment_partitions(
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


def connector_peer_pin_heuristic_coverage(
    observed: NetlistContract,
    netlist_sha256: str,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
    *,
    repeated_function_finding_count: int,
    peer_pin_outlier_finding_count: int,
    peer_pin_divergence_finding_count: int,
) -> ConnectorPeerPinHeuristicCoverage:
    """Summarize exact-symbol pin and named-function comparisons over this netlist."""
    candidate_references = connector_candidate_references(observed, declared_references)
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    fitted_references = tuple(
        reference for reference in candidate_references if reference.casefold() not in unpopulated
    )
    symbols_by_reference = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_inventory = {
        reference.casefold(): tuple(pin_numbers)
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    pins_by_reference: dict[str, set[str]] = {}
    for reference in fitted_references:
        pins = set(pin_inventory.get(reference.casefold(), ()))
        pins.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        pins_by_reference[reference.casefold()] = pins

    references_by_symbol: dict[str, set[str]] = {}
    for reference in fitted_references:
        symbol = symbols_by_reference.get(reference.casefold())
        if symbol is None:
            continue
        symbol_key = symbol.casefold()
        references_by_symbol.setdefault(symbol_key, set()).add(reference)
    exact_symbol_groups = tuple(
        (symbol_key, tuple(sorted(references, key=lambda item: (item.casefold(), item))))
        for symbol_key, references in sorted(references_by_symbol.items())
        if len(references) >= 2
    )
    observed_pin_numbers_by_reference: dict[str, set[str]] = {}
    for pin in observed.pin_functions:
        reference, pin_number = pin.rsplit(".", 1)
        observed_pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(
            pin_number.casefold()
        )
    for assignments in (*observed.nets.values(), *observed.unconnected_nets.values()):
        for pin in assignments:
            reference, pin_number = pin.rsplit(".", 1)
            observed_pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(
                pin_number.casefold()
            )
    incomplete_inventory_reference_set: set[str] = set()
    for _, references in exact_symbol_groups:
        inventories_by_reference = {
            reference: frozenset(
                pin.casefold() for pin in pin_inventory.get(reference.casefold(), ())
            )
            for reference in references
        }
        inventory_counts: dict[frozenset[str], int] = {}
        for inventory in inventories_by_reference.values():
            inventory_counts[inventory] = inventory_counts.get(inventory, 0) + 1
        highest_inventory_count = max(inventory_counts.values(), default=0)
        most_common_inventories = tuple(
            inventory
            for inventory, count in inventory_counts.items()
            if count == highest_inventory_count
        )
        if len(inventory_counts) > 1:
            if len(most_common_inventories) == 1:
                incomplete_inventory_reference_set.update(
                    reference
                    for reference, inventory in inventories_by_reference.items()
                    if inventory != most_common_inventories[0]
                )
            else:
                incomplete_inventory_reference_set.update(references)
        for reference, inventory in inventories_by_reference.items():
            if not inventory or not observed_pin_numbers_by_reference.get(
                reference.casefold(), set()
            ).issubset(inventory):
                incomplete_inventory_reference_set.add(reference)
    incomplete_inventory_references = tuple(
        sorted(incomplete_inventory_reference_set, key=lambda item: (item.casefold(), item))
    )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    peer_pin_group_count = 0
    peer_pin_groups_with_unknown_function_count = 0
    peer_pin_groups_with_meaningful_functions_count = 0
    peer_pin_groups_with_common_assignment_count = 0
    peer_pin_groups_with_different_assignments_count = 0
    peer_pin_groups_all_unassigned_count = 0
    peer_pin_groups_with_open_assignment_count = 0
    for _, references in exact_symbol_groups:
        pin_numbers: set[str] = set()
        for reference in references:
            pin_numbers.update(pins_by_reference[reference.casefold()])
        for pin_number in sorted(pin_numbers, key=lambda item: (item.casefold(), item)):
            assignments = {
                f"{reference}.{pin_number}": tuple(
                    sorted(pin_nets.get(f"{reference}.{pin_number}", ()))
                )
                for reference in references
                if pin_number in pins_by_reference[reference.casefold()]
            }
            for _, scoped_assignments, _ in _peer_assignment_partitions(
                assignments,
                peer_assignment_groups,
            ):
                if len(scoped_assignments) < 2:
                    continue
                peer_pin_group_count += 1
                unknown_function = any(
                    not _has_meaningful_pin_function(pin_functions.get(pin.casefold()))
                    for pin in scoped_assignments
                )
                if unknown_function:
                    peer_pin_groups_with_unknown_function_count += 1
                else:
                    peer_pin_groups_with_meaningful_functions_count += 1
                assignments_by_peer = tuple(scoped_assignments.values())
                if any(not nets for nets in assignments_by_peer):
                    peer_pin_groups_with_open_assignment_count += 1
                if all(not nets for nets in assignments_by_peer):
                    peer_pin_groups_all_unassigned_count += 1
                elif len(set(assignments_by_peer)) > 1:
                    peer_pin_groups_with_different_assignments_count += 1
                else:
                    peer_pin_groups_with_common_assignment_count += 1

    repeated_function_groups = similar_connector_pin_groups(
        observed,
        declared_references,
        reviewed_connector_pins,
        peer_assignment_groups,
        include_consistent=True,
    )
    repeated_function_groups_with_common_assignment_count = 0
    repeated_function_groups_with_different_assignments_count = 0
    repeated_function_groups_all_unassigned_count = 0
    repeated_function_groups_with_open_assignment_count = 0
    for group in repeated_function_groups:
        assignments = tuple(group.pins.values())
        if any(not nets for nets in assignments):
            repeated_function_groups_with_open_assignment_count += 1
        if all(not nets for nets in assignments):
            repeated_function_groups_all_unassigned_count += 1
        elif len(set(assignments)) > 1:
            repeated_function_groups_with_different_assignments_count += 1
        else:
            repeated_function_groups_with_common_assignment_count += 1

    if not candidate_references:
        status = "NO_CONNECTOR_CANDIDATES"
    elif not fitted_references:
        status = "NO_FITTED_CONNECTORS"
    elif not exact_symbol_groups:
        status = "NO_EXACT_SYMBOL_PEERS"
    elif incomplete_inventory_references:
        status = "INCOMPLETE_PIN_INVENTORY"
    elif not peer_pin_group_count:
        status = "NO_COMPARABLE_PIN_GROUPS"
    else:
        status = "EVALUATED"
    return ConnectorPeerPinHeuristicCoverage(
        status=status,
        netlist_sha256=netlist_sha256,
        scope=(
            "Named connector functions are compared only by the existing bounded role or exact "
            "symbol/function rules. Generic peer assignments compare exact symbol and pin number. "
            "Coverage records evaluated evidence; it does not assert that peer nets must match."
        ),
        connector_candidate_count=len(candidate_references),
        fitted_connector_count=len(fitted_references),
        exact_symbol_peer_group_count=len(exact_symbol_groups),
        exact_symbol_pin_group_count=peer_pin_group_count,
        exact_symbol_pin_groups_with_unknown_function_count=(
            peer_pin_groups_with_unknown_function_count
        ),
        exact_symbol_pin_groups_with_meaningful_functions_count=(
            peer_pin_groups_with_meaningful_functions_count
        ),
        exact_symbol_pin_groups_with_common_assignment_count=(
            peer_pin_groups_with_common_assignment_count
        ),
        exact_symbol_pin_groups_with_different_assignments_count=(
            peer_pin_groups_with_different_assignments_count
        ),
        exact_symbol_pin_groups_all_unassigned_count=peer_pin_groups_all_unassigned_count,
        exact_symbol_pin_groups_with_open_assignment_count=(
            peer_pin_groups_with_open_assignment_count
        ),
        incomplete_pin_inventory_references=incomplete_inventory_references,
        repeated_function_group_count=len(repeated_function_groups),
        repeated_function_groups_with_common_assignment_count=(
            repeated_function_groups_with_common_assignment_count
        ),
        repeated_function_groups_with_different_assignments_count=(
            repeated_function_groups_with_different_assignments_count
        ),
        repeated_function_groups_all_unassigned_count=repeated_function_groups_all_unassigned_count,
        repeated_function_groups_with_open_assignment_count=(
            repeated_function_groups_with_open_assignment_count
        ),
        repeated_function_finding_count=repeated_function_finding_count,
        peer_pin_outlier_finding_count=peer_pin_outlier_finding_count,
        peer_pin_divergence_finding_count=peer_pin_divergence_finding_count,
    )


@dataclass(frozen=True)
class ConnectorReturnCoverage:
    reference: str
    symbol: str
    connected_pin_count: int
    pins: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class UnconnectedNamedConnectorPin:
    pin: str
    function: str
    category: str
    role_source: str = "native_symbol"


@dataclass(frozen=True)
class UnconnectedGenericPowerInputConnectorPin:
    pin: str
    symbol: str
    function: str | None
    electrical_type: str


@dataclass(frozen=True)
class ConnectorPeerPinAssignmentOutlier:
    symbol: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    outlier_pins: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


def _unique_peer_pin_majority(
    assignments: dict[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    counts: dict[tuple[str, ...], int] = {}
    for signature in assignments.values():
        counts[signature] = counts.get(signature, 0) + 1
    highest_count = max(counts.values(), default=0)
    leaders = tuple(signature for signature, count in counts.items() if count == highest_count)
    if highest_count < 2 or highest_count == len(assignments) or len(leaders) != 1:
        return None
    return leaders[0]


def _peer_assignment_partitions(
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


def connector_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[ConnectorPeerPinAssignmentOutlier, ...]:
    """Find exact-symbol peer pins with incomplete or minority net assignments.

    This rule is reserved for pins whose function metadata is absent or only
    contains a generic Pin_N placeholder, since the named-function comparison
    already covers pins with meaningful roles. A matching library symbol and
    pin number identify comparable contacts, but do not establish that their
    nets must be common.
    """
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    grouped: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
    symbols: dict[str, str] = {}
    functions_by_pin = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        pin_numbers = set(observed.component_pin_numbers.get(reference, ()))
        pin_numbers.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        for pin_number in pin_numbers:
            pin = f"{reference}.{pin_number}"
            grouped.setdefault((symbol.casefold(), pin_number), {})[pin] = tuple(
                sorted(pin_nets.get(pin, ()))
            )
            symbols[symbol.casefold()] = symbol

    results: list[ConnectorPeerPinAssignmentOutlier] = []
    for (symbol_key, pin_number), assignments in sorted(grouped.items()):
        for peer_group, scoped_assignments, peer_review in _peer_assignment_partitions(
            assignments,
            peer_assignment_groups,
        ):
            if len(scoped_assignments) < 2 or len(set(scoped_assignments.values())) == 1:
                continue
            # A named-function comparison is more direct and already reports these
            # mismatches. This check fills the gap where at least one peer function
            # is absent or only has a generic Pin_N placeholder.
            if all(
                _has_meaningful_pin_function(functions_by_pin.get(pin.casefold()))
                for pin in scoped_assignments
            ):
                continue

            signatures = list(scoped_assignments.values())
            if any(not signature for signature in signatures):
                if not any(signature for signature in signatures):
                    continue
                outlier_pins = tuple(
                    sorted(pin for pin, nets in scoped_assignments.items() if not nets)
                )
            else:
                majority = _unique_peer_pin_majority(scoped_assignments)
                if majority is None:
                    continue
                outlier_pins = tuple(
                    sorted(pin for pin, nets in scoped_assignments.items() if nets != majority)
                )
            if not outlier_pins:
                continue
            results.append(
                ConnectorPeerPinAssignmentOutlier(
                    symbol=symbols[symbol_key],
                    pin_number=pin_number,
                    assignments=dict(sorted(scoped_assignments.items())),
                    outlier_pins=outlier_pins,
                    peer_assignment_group=peer_group,
                    peer_assignment_basis=peer_review,
                )
            )
    return tuple(results)


@dataclass(frozen=True)
class ConnectorPeerPinAssignmentDivergence:
    symbol: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    missing_function_pins: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


def connector_peer_pin_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[ConnectorPeerPinAssignmentDivergence, ...]:
    """Review assigned peer contacts that differ when at least one role is unknown.

    The outlier rule above needs a majority assignment to identify a minority
    peer. This lower-confidence check retains the exact-symbol/pin-number
    boundary, but only reports fully assigned groups with conflicting nets and
    absent or generic pin-function metadata. It does not infer a required
    connection.
    """
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    grouped: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
    symbols: dict[str, str] = {}
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        pin_numbers = set(observed.component_pin_numbers.get(reference, ()))
        pin_numbers.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        for pin_number in pin_numbers:
            pin = f"{reference}.{pin_number}"
            grouped.setdefault((symbol.casefold(), pin_number.casefold()), {})[pin] = tuple(
                sorted(pin_nets.get(pin.casefold(), ()))
            )
            symbols[symbol.casefold()] = symbol

    results: list[ConnectorPeerPinAssignmentDivergence] = []
    for (symbol_key, pin_number_key), assignments in sorted(grouped.items()):
        for peer_group, scoped_assignments, peer_review in _peer_assignment_partitions(
            assignments,
            peer_assignment_groups,
        ):
            if len(scoped_assignments) < 2 or any(not nets for nets in scoped_assignments.values()):
                continue
            if len(set(scoped_assignments.values())) == 1:
                continue
            if _unique_peer_pin_majority(scoped_assignments) is not None:
                continue
            missing_function_pins = tuple(
                sorted(
                    pin
                    for pin in scoped_assignments
                    if not _has_meaningful_pin_function(pin_functions.get(pin.casefold()))
                )
            )
            if (
                len(missing_function_pins) < 1
                or len(scoped_assignments) - len(missing_function_pins) >= 2
            ):
                continue
            pin_number = next(
                pin.rsplit(".", 1)[1]
                for pin in scoped_assignments
                if pin.rsplit(".", 1)[1].casefold() == pin_number_key
            )
            results.append(
                ConnectorPeerPinAssignmentDivergence(
                    symbol=symbols[symbol_key],
                    pin_number=pin_number,
                    assignments=dict(sorted(scoped_assignments.items())),
                    missing_function_pins=missing_function_pins,
                    peer_assignment_group=peer_group,
                    peer_assignment_basis=peer_review,
                )
            )
    return tuple(results)


def unconnected_named_connector_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
) -> tuple[UnconnectedNamedConnectorPin, ...]:
    """Find unassigned native or project-mapped connector supply/return pins."""
    reviewed_connector_pins = reviewed_connector_pins or {}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    connected = {pin for pins in observed.nets.values() for pin in pins}
    results: list[UnconnectedNamedConnectorPin] = []
    for pin in sorted(set(observed.pin_functions) | set(reviewed_connector_pins)):
        function = observed.pin_functions.get(pin, "")
        reference = pin.rsplit(".", 1)[0]
        if (
            reference.casefold() not in connector_references
            or reference not in observed.component_symbols
            or reference.casefold() in unpopulated
            or pin in connected
        ):
            continue
        category = "return" if _is_return_function(function) else None
        if category is None and _is_named_supply_function(function):
            category = "supply"
        role_source = "native_symbol"
        mapped = reviewed_connector_pins.get(pin)
        if (
            category is None
            and mapped is not None
            and mapped.role in {"return", "supply"}
            and _pin_function_is_generic(function)
        ):
            category = mapped.role
            function = mapped.interface_signal
            role_source = "project_interface"
        if category is not None:
            results.append(
                UnconnectedNamedConnectorPin(
                    pin=pin,
                    function=function,
                    category=category,
                    role_source=role_source,
                )
            )
    return tuple(sorted(results, key=lambda item: (item.category, item.pin, item.function)))


def unconnected_generic_power_input_connector_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    excluded_pins: frozenset[str] = frozenset(),
) -> tuple[UnconnectedGenericPowerInputConnectorPin, ...]:
    """Find unassigned generic connector pins with the native ``power_in`` type."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    symbols_by_reference = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connected = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    excluded = {pin.casefold() for pin in excluded_pins}
    results: list[UnconnectedGenericPowerInputConnectorPin] = []
    for pin, electrical_type in observed.pin_electrical_types.items():
        pin_key = pin.casefold()
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        function = pin_functions.get(pin_key)
        symbol = symbols_by_reference.get(reference_key)
        if (
            electrical_type.strip().casefold() != "power_in"
            or reference_key not in connector_references
            or reference_key in dnp
            or pin_key in connected
            or pin_key in excluded
            or not _pin_function_is_generic(function)
            or symbol is None
        ):
            continue
        results.append(
            UnconnectedGenericPowerInputConnectorPin(
                pin=pin,
                symbol=symbol[1],
                function=function,
                electrical_type="power_in",
            )
        )
    return tuple(sorted(results, key=lambda item: (item.pin.casefold(), item.pin)))


@dataclass(frozen=True)
class UnconnectedGenericPowerInputComponentPin:
    pin: str
    symbol: str
    function: str | None
    electrical_type: str


def unconnected_generic_power_input_component_pins(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UnconnectedGenericPowerInputComponentPin, ...]:
    """Find unassigned generic ``power_in`` pins on fitted non-connectors."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    component_references = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connected = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    results: list[UnconnectedGenericPowerInputComponentPin] = []
    for pin, electrical_type in observed.pin_electrical_types.items():
        pin_key = pin.casefold()
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        symbol = symbols.get(reference_key)
        if (
            "." not in pin
            or electrical_type.strip().casefold() != "power_in"
            or reference_key not in component_references
            or reference_key in connector_references
            or reference_key in unpopulated
            or pin_key in connected
            or not _pin_function_is_generic(functions.get(pin_key))
            or symbol is None
        ):
            continue
        results.append(
            UnconnectedGenericPowerInputComponentPin(
                pin=pin,
                symbol=symbol,
                function=functions.get(pin_key),
                electrical_type="power_in",
            )
        )
    return tuple(sorted(results, key=lambda item: (item.pin.casefold(), item.pin)))


@dataclass(frozen=True)
class UnconnectedNamedComponentPin:
    pin: str
    function: str
    category: str


def unconnected_named_component_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[UnconnectedNamedComponentPin, ...]:
    """Find named supply/return pins on non-connector parts with no net."""
    connected = {pin for pins in observed.nets.values() for pin in pins}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    results: list[UnconnectedNamedComponentPin] = []
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", 1)[0]
        if (
            reference not in observed.components
            or reference.casefold() in connector_references
            or pin in connected
        ):
            continue
        category = "return" if _is_return_function(function) else None
        if category is None and _is_named_supply_function(function):
            category = "supply"
        if category is not None:
            results.append(
                UnconnectedNamedComponentPin(
                    pin=pin,
                    function=function,
                    category=category,
                )
            )
    return tuple(sorted(results, key=lambda item: (item.category, item.pin, item.function)))


@dataclass(frozen=True)
class RepeatedComponentSupplyPins:
    reference: str
    symbol: str
    function: str
    pins: dict[str, tuple[str, ...]]


def component_supply_pins_on_different_nets(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[RepeatedComponentSupplyPins, ...]:
    """Find same-component supply pins with matching roles but distinct nets."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    grouped: dict[tuple[str, str], list[tuple[str, str, str, tuple[str, ...]]]] = {}
    for pin, function in observed.pin_functions.items():
        if "." not in pin:
            continue
        reference = pin.rsplit(".", 1)[0]
        symbol = observed.component_symbols.get(reference)
        if (
            symbol is None
            or reference not in observed.components
            or reference.casefold() in unpopulated
            or reference.casefold() in connector_references
        ):
            continue
        supply_key = power_function_key(function)
        if supply_key is None:
            continue
        grouped.setdefault((reference.casefold(), supply_key), []).append(
            (pin, reference, function, tuple(sorted(pin_nets.get(pin, ()))))
        )

    results: list[RepeatedComponentSupplyPins] = []
    for entries in grouped.values():
        # Open pins have a more specific existing finding. Keep this rule for
        # assigned-but-disagreeing rails, where native ERC may have no conflict.
        if len(entries) < 2 or any(not nets for _, _, _, nets in entries):
            continue
        if len({nets for _, _, _, nets in entries}) == 1 and all(
            len(nets) == 1 for _, _, _, nets in entries
        ):
            continue
        entries.sort()
        _, reference, function, _ = entries[0]
        symbol = observed.component_symbols[reference]
        results.append(
            RepeatedComponentSupplyPins(
                reference=reference,
                symbol=symbol,
                function=function,
                pins={pin: nets for pin, _, _, nets in entries},
            )
        )
    return tuple(sorted(results, key=lambda item: (item.reference, item.function)))


@dataclass(frozen=True)
class PeerPowerPinAssignmentDivergence:
    symbol: str
    pin_number: str
    function: str
    role: str
    assignments: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class PeerPinAssignmentOutlier:
    symbol: str
    pin_number: str
    electrical_type: str
    assignments: dict[str, tuple[str, ...]]
    pin_function: str | None = None


def _component_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    electrical_types: frozenset[str],
    require_pin_functions: bool = False,
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open typed pin among fitted peers of one exact symbol.

    A same-symbol, same-pin assignment is a review clue only. The other
    instances may intentionally use that pin differently or leave it open.
    """
    accepted_types = {value.strip().casefold() for value in electrical_types}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    known_components = {reference.casefold() for reference in observed.components}
    references_by_symbol: dict[str, list[str]] = {}
    symbols_by_key: dict[str, str] = {}
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        if (
            reference_key not in known_components
            or reference_key in unpopulated
            or reference_key in connector_references
        ):
            continue
        symbol_key = symbol.casefold()
        references_by_symbol.setdefault(symbol_key, []).append(reference)
        symbols_by_key[symbol_key] = symbol

    inventories = {
        reference.casefold(): tuple(sorted(numbers, key=str.casefold))
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_electrical_types = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    results: list[PeerPinAssignmentOutlier] = []
    for symbol_key, references in sorted(references_by_symbol.items()):
        peers = tuple(sorted(references, key=str.casefold))
        if len(peers) < 2:
            continue
        peer_inventories = tuple(inventories.get(reference.casefold(), ()) for reference in peers)
        if (
            not peer_inventories[0]
            or any(not numbers for numbers in peer_inventories)
            or any(
                {number.casefold() for number in numbers}
                != {number.casefold() for number in peer_inventories[0]}
                for numbers in peer_inventories[1:]
            )
            or len({number.casefold() for number in peer_inventories[0]})
            != len(peer_inventories[0])
        ):
            continue

        for pin_number in peer_inventories[0]:
            pins = tuple(f"{reference}.{pin_number}" for reference in peers)
            peer_types = tuple(pin_electrical_types.get(pin.casefold()) for pin in pins)
            if (
                any(electrical_type not in accepted_types for electrical_type in peer_types)
                or len(set(peer_types)) != 1
            ):
                continue
            peer_functions = tuple(functions.get(pin.casefold()) for pin in pins)
            if (
                require_pin_functions
                and any(function is None or not function.strip() for function in peer_functions)
            ) or len(
                {
                    function.casefold() if function is not None else None
                    for function in peer_functions
                }
            ) > 1:
                continue
            assignments = {
                pin: tuple(sorted(pin_nets.get(pin.casefold(), ()), key=str.casefold))
                for pin in pins
            }
            if any(len(nets) > 1 for nets in assignments.values()):
                continue
            open_pins = tuple(pin for pin, nets in assignments.items() if not nets)
            assigned_pins = tuple(pin for pin, nets in assignments.items() if nets)
            if not open_pins or not assigned_pins:
                continue
            if any(
                function is not None
                and (_is_named_supply_function(function) or _is_return_function(function))
                for pin in open_pins
                for function in (functions.get(pin.casefold()),)
            ):
                # Preserve the more specific existing named supply/return prompt.
                continue
            results.append(
                PeerPinAssignmentOutlier(
                    symbol=symbols_by_key[symbol_key],
                    pin_number=pin_number,
                    electrical_type=peer_types[0] or "",
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: item[0].casefold())
                    ),
                    pin_function=peer_functions[0],
                )
            )
    return tuple(
        sorted(
            results,
            key=lambda item: (item.symbol.casefold(), item.pin_number.casefold()),
        )
    )


def component_peer_power_output_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native power-output pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"power_out"}),
    )


def component_peer_signal_output_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native signal-output pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"output"}),
    )


def component_peer_signal_input_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native signal-input pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"input", "input_low"}),
        require_pin_functions=True,
    )


def component_peer_bidirectional_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native bidirectional pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"bidirectional"}),
        require_pin_functions=True,
    )


def component_peer_power_pin_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPowerPinAssignmentDivergence, ...]:
    """Find split recognized power pins across fitted peers with one exact symbol.

    Exact symbol, pin number, and named power function make a review candidate;
    they do not establish that the peers must use a common electrical domain.
    Incomplete pin inventories, unrecognized functions, open pins, and DNP parts
    are left to other checks or explicit project review.
    """
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, str] = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
    }
    pin_numbers_by_reference: dict[str, set[str]] = {
        reference.casefold(): set(pin_numbers)
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    for pin in observed.pin_functions:
        if "." not in pin:
            continue
        reference, pin_number = pin.rsplit(".", 1)
        pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(pin_number)

    references_by_symbol: dict[str, list[str]] = {}
    symbol_names: dict[str, str] = {}
    known_components = {reference.casefold() for reference in observed.components}
    for reference, symbol in observed.component_symbols.items():
        if (
            reference.casefold() not in known_components
            or reference.casefold() in unpopulated
            or reference.casefold() in connector_references
        ):
            continue
        references_by_symbol.setdefault(symbol.casefold(), []).append(reference)
        symbol_names[symbol.casefold()] = symbol

    results: list[PeerPowerPinAssignmentDivergence] = []
    for symbol_key, references in sorted(references_by_symbol.items()):
        peer_references = tuple(sorted(references, key=str.casefold))
        if len(peer_references) < 2:
            continue
        shared_pin_numbers: set[str] = set(
            pin_numbers_by_reference.get(peer_references[0].casefold(), set())
        )
        for reference in peer_references[1:]:
            shared_pin_numbers.intersection_update(
                pin_numbers_by_reference.get(reference.casefold(), set())
            )
        for pin_number in sorted(shared_pin_numbers, key=str.casefold):
            pins = tuple(f"{reference}.{pin_number}" for reference in peer_references)
            functions: tuple[str | None, ...] = tuple(
                functions_by_pin.get(pin.casefold()) for pin in pins
            )
            if any(function is None for function in functions):
                continue
            typed_functions: tuple[str, ...] = tuple(
                function for function in functions if function is not None
            )
            if all(_is_return_function(function) for function in typed_functions):
                role = "ground/return"
            else:
                supply_keys: tuple[str | None, ...] = tuple(
                    power_function_key(function) for function in typed_functions
                )
                if any(key is None for key in supply_keys) or len(set(supply_keys)) != 1:
                    continue
                role = "supply"
            assignments: dict[str, tuple[str, ...]] = {
                pin: tuple(sorted(pin_nets.get(pin.casefold(), ()))) for pin in pins
            }
            if any(not nets for nets in assignments.values()):
                continue
            if len(set(assignments.values())) < 2:
                continue
            results.append(
                PeerPowerPinAssignmentDivergence(
                    symbol=symbol_names[symbol_key],
                    pin_number=pin_number,
                    function=typed_functions[0],
                    role=role,
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: item[0].casefold())
                    ),
                )
            )
    return tuple(
        sorted(
            results,
            key=lambda item: (item.symbol.casefold(), item.pin_number.casefold(), item.role),
        )
    )


def connectors_without_connected_return(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
) -> tuple[ConnectorReturnCoverage, ...]:
    """Flag multi-conductor connectors with no connected native or mapped return."""
    reviewed_connector_pins = reviewed_connector_pins or {}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    symbols_by_reference = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    connected_signal_pins: dict[str, set[str]] = {}
    connected_returns: dict[str, set[str]] = {}
    all_return_pins: dict[str, set[str]] = {}
    pin_nets: dict[str, set[str]] = {}

    for pin in sorted(set(observed.pin_functions) | set(reviewed_connector_pins)):
        function = observed.pin_functions.get(pin, "")
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        if reference.casefold() not in symbols_by_reference:
            continue
        mapped = reviewed_connector_pins.get(pin)
        if _is_return_function(function) or (
            mapped is not None and mapped.role == "return" and _pin_function_is_generic(function)
        ):
            all_return_pins.setdefault(reference, set()).add(pin)

    for net, pins in observed.nets.items():
        for pin in pins:
            reference = pin.rsplit(".", 1)[0]
            if (
                reference.casefold() not in connector_references
                or reference.casefold() in unpopulated
            ):
                continue
            if reference.casefold() not in symbols_by_reference:
                continue
            pin_nets.setdefault(pin, set()).add(net)
            function = observed.pin_functions.get(pin, "")
            mapped = reviewed_connector_pins.get(pin)
            if function and _is_shield_function(function):
                continue
            connected_signal_pins.setdefault(reference, set()).add(pin)
            if _is_return_function(function) or (
                mapped is not None
                and mapped.role == "return"
                and _pin_function_is_generic(function)
            ):
                connected_returns.setdefault(reference, set()).add(pin)

    results: list[ConnectorReturnCoverage] = []
    for reference, pins in sorted(connected_signal_pins.items()):
        if len(pins) < 3 or connected_returns.get(reference):
            continue
        evidence_pins = pins | all_return_pins.get(reference, set())
        results.append(
            ConnectorReturnCoverage(
                reference=reference,
                symbol=symbols_by_reference[reference.casefold()][1],
                connected_pin_count=len(pins),
                pins={pin: tuple(sorted(pin_nets.get(pin, ()))) for pin in sorted(evidence_pins)},
            )
        )
    return tuple(results)
