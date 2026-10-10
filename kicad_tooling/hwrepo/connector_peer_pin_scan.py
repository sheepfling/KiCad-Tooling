"""Source-bound scans for comparable connector peer pins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .connector_identity import connector_candidate_references, partition_peer_assignments
from .models import NetlistContract


@dataclass(frozen=True)
class ConnectorPeerPinAssignmentOutlier:
    symbol: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    outlier_pins: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol"
    peer_identity: str = ""
    peer_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorPeerPinAssignmentDivergence:
    symbol: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    missing_function_pins: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol"
    peer_identity: str = ""
    peer_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ConnectorPartIdPeerPinGroup:
    part_id: str
    pin_number: str
    pin_function: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ConnectorPartIdPeerPinScan:
    candidate_group_count: int
    incomplete_component_identity_group_count: int
    incomplete_pin_inventory_group_count: int
    incomplete_pin_metadata_group_count: int
    eligible_peer_group_count: int
    incomplete_pin_inventory_references: tuple[str, ...]
    pin_groups: tuple[_ConnectorPartIdPeerPinGroup, ...]


def unique_peer_pin_majority(
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


def scan_connector_part_id_peer_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> _ConnectorPartIdPeerPinScan:
    """Compare connector aliases only after exact source identity and pin metadata match."""
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    components = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    references_by_part_id: dict[str, list[str]] = {}
    part_ids: dict[str, set[str]] = {}
    for reference, component in observed.components.items():
        reference_key = reference.casefold()
        if (
            reference_key not in connector_references
            or reference_key in unpopulated
            or reference_key not in symbols
            or component.part_id is None
            or not component.part_id.strip()
        ):
            continue
        part_id = component.part_id.strip()
        part_key = part_id.casefold()
        references_by_part_id.setdefault(part_key, []).append(reference)
        part_ids.setdefault(part_key, set()).add(part_id)

    candidate_groups: list[tuple[str, str, tuple[str, ...]]] = []
    for part_key, references in sorted(references_by_part_id.items()):
        peers = tuple(sorted(references, key=lambda item: (item.casefold(), item)))
        peer_symbols = {symbols[reference.casefold()].casefold() for reference in peers}
        if len(peers) < 2 or len(peer_symbols) < 2:
            continue
        display_id = min(part_ids[part_key], key=lambda item: (item.casefold(), item))
        candidate_groups.append((part_key, display_id, peers))

    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_types = {
        pin.casefold(): electrical_type
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    observed_pin_numbers: dict[str, set[str]] = {}
    for pin in observed.pin_functions:
        reference, pin_number = pin.rsplit(".", 1)
        observed_pin_numbers.setdefault(reference.casefold(), set()).add(pin_number.casefold())
    for assignments in (*observed.nets.values(), *observed.unconnected_nets.values()):
        for pin in assignments:
            reference, pin_number = pin.rsplit(".", 1)
            observed_pin_numbers.setdefault(reference.casefold(), set()).add(pin_number.casefold())

    incomplete_identity_count = 0
    incomplete_inventory_count = 0
    incomplete_metadata_count = 0
    eligible_peer_group_count = 0
    incomplete_inventory_references: set[str] = set()
    pin_groups: list[_ConnectorPartIdPeerPinGroup] = []
    for part_key, display_id, peers in candidate_groups:
        peer_components = tuple(components[reference.casefold()] for reference in peers)
        values = {component.value.strip().casefold() for component in peer_components}
        footprints = {component.footprint.strip().casefold() for component in peer_components}
        if len(values) != 1 or "" in values or len(footprints) != 1 or "" in footprints:
            incomplete_identity_count += 1
            continue

        raw_inventories = {
            reference.casefold(): tuple(
                number
                for candidate, numbers in observed.component_pin_numbers.items()
                if candidate.casefold() == reference.casefold()
                for number in numbers
            )
            for reference in peers
        }
        folded_inventories = {
            reference: tuple(number.casefold() for number in numbers)
            for reference, numbers in raw_inventories.items()
        }
        inventory_sets = {frozenset(numbers) for numbers in folded_inventories.values()}
        invalid_inventory = (
            any(not numbers for numbers in folded_inventories.values())
            or any(len(set(numbers)) != len(numbers) for numbers in folded_inventories.values())
            or len(inventory_sets) != 1
            or any(
                not observed_pin_numbers.get(reference.casefold(), set()).issubset(
                    set(folded_inventories[reference.casefold()])
                )
                for reference in peers
            )
        )
        if invalid_inventory:
            incomplete_inventory_count += 1
            incomplete_inventory_references.update(peers)
            continue

        pin_numbers = tuple(
            sorted(next(iter(inventory_sets)), key=lambda item: (item.casefold(), item))
        )
        displayed_numbers = {
            reference.casefold(): {
                number.casefold(): number for number in raw_inventories[reference.casefold()]
            }
            for reference in peers
        }
        pin_metadata: dict[str, tuple[str, str]] = {}
        metadata_invalid = False
        for pin_number in pin_numbers:
            functions: list[str] = []
            electrical_types: list[str] = []
            for reference in peers:
                pin = f"{reference}.{displayed_numbers[reference.casefold()][pin_number]}"
                function = pin_functions.get(pin.casefold())
                electrical_type = pin_types.get(pin.casefold())
                if (
                    function is None
                    or not function.strip()
                    or electrical_type is None
                    or not electrical_type.strip()
                ):
                    metadata_invalid = True
                    continue
                functions.append(function)
                electrical_types.append(electrical_type)
            if (
                len({function.strip().casefold() for function in functions}) != 1
                or len({electrical_type.strip().casefold() for electrical_type in electrical_types})
                != 1
            ):
                metadata_invalid = True
            if functions and electrical_types:
                pin_metadata[pin_number] = (functions[0], electrical_types[0])
        if metadata_invalid:
            incomplete_metadata_count += 1
            continue

        eligible_peer_group_count += 1
        peer_symbols = tuple(
            sorted(
                {symbols[reference.casefold()] for reference in peers},
                key=lambda item: (item.casefold(), item),
            )
        )
        for pin_number in pin_numbers:
            assignments = {
                f"{reference}.{displayed_numbers[reference.casefold()][pin_number]}": tuple(
                    sorted(
                        pin_nets.get(
                            f"{reference}.{displayed_numbers[reference.casefold()][pin_number]}".casefold(),
                            (),
                        ),
                        key=lambda item: (item.casefold(), item),
                    )
                )
                for reference in peers
            }
            for peer_group, scoped_assignments, peer_review in partition_peer_assignments(
                assignments,
                peer_assignment_groups,
            ):
                if len(scoped_assignments) < 2:
                    continue
                pin_groups.append(
                    _ConnectorPartIdPeerPinGroup(
                        part_id=display_id,
                        pin_number=pin_number,
                        pin_function=pin_metadata[pin_number][0],
                        assignments=dict(
                            sorted(
                                scoped_assignments.items(),
                                key=lambda item: (item[0].casefold(), item[0]),
                            )
                        ),
                        symbols=peer_symbols,
                        peer_assignment_group=peer_group,
                        peer_assignment_basis=peer_review,
                    )
                )
    return _ConnectorPartIdPeerPinScan(
        candidate_group_count=len(candidate_groups),
        incomplete_component_identity_group_count=incomplete_identity_count,
        incomplete_pin_inventory_group_count=incomplete_inventory_count,
        incomplete_pin_metadata_group_count=incomplete_metadata_count,
        eligible_peer_group_count=eligible_peer_group_count,
        incomplete_pin_inventory_references=tuple(
            sorted(incomplete_inventory_references, key=lambda item: (item.casefold(), item))
        ),
        pin_groups=tuple(
            sorted(
                pin_groups,
                key=lambda item: (
                    item.part_id.casefold(),
                    item.pin_number.casefold(),
                    tuple(sorted(pin.casefold() for pin in item.assignments)),
                ),
            )
        ),
    )
