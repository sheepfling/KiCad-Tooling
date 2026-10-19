"""Conservative peer-pin review across connector symbol aliases without PART_ID."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .connector_identity import (
    connector_candidate_references,
    has_meaningful_pin_function,
    partition_peer_assignments,
)
from .models import NetlistContract


@dataclass(frozen=True)
class ConnectorFootprintPeerPinDivergence:
    """A generic pin assignment difference inside a bounded alias candidate group."""

    footprint: str
    value: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinOpenOutlier:
    """A generic contact assigned on some, but not all, footprint-alias peers."""

    footprint: str
    value: str
    pin_number: str
    assignments: dict[str, tuple[str, ...]]
    open_pins: tuple[str, ...]
    symbols: tuple[str, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorFootprintPeerPinScan:
    """Coverage and review candidates derived from one native netlist snapshot."""

    candidate_group_count: int
    incomplete_pin_inventory_group_count: int
    incomplete_pin_metadata_group_count: int
    eligible_peer_group_count: int
    peer_scope_group_count: int
    evaluated_pin_group_count: int
    compared_pin_group_count: int
    common_assignment_pin_group_count: int
    different_assignment_pin_group_count: int
    unassigned_assignment_pin_group_count: int
    ambiguous_assignment_pin_group_count: int
    generic_different_assignment_pin_group_count: int
    non_generic_different_assignment_pin_group_count: int
    common_anchor_group_count: int
    unanchored_different_assignment_pin_group_count: int
    finding_count: int
    open_peer_pin_group_count: int
    unanchored_open_peer_pin_group_count: int
    open_outlier_finding_count: int
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    open_outliers: tuple[ConnectorFootprintPeerPinOpenOutlier, ...]


def _observed_pin_numbers(observed: NetlistContract) -> dict[str, set[str]]:
    """Collect all pin references that must be represented by a full inventory."""
    found: dict[str, set[str]] = {}
    pin_groups = (
        observed.pin_functions,
        observed.pin_electrical_types,
        *observed.nets.values(),
        *observed.unconnected_nets.values(),
    )
    for assignments in pin_groups:
        pins = assignments if not isinstance(assignments, Mapping) else assignments.keys()
        for pin in pins:
            reference, separator, number = pin.rpartition(".")
            if separator and reference and number:
                found.setdefault(reference.casefold(), set()).add(number.casefold())
    return found


def scan_connector_footprint_peer_pin_assignments(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> ConnectorFootprintPeerPinScan:
    """Review split generic contacts only when matching footprint peers share an anchor.

    Matching value, footprint, pin inventory, and native pin metadata are
    similarity clues only. This scan requires complete matching metadata and
    an exact shared net on another pin before it emits a review candidate. It
    excludes PART_ID-bearing components, which use the separately reviewed
    exact-part alias checks.
    """
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    components = {reference.casefold(): item for reference, item in observed.components.items()}
    symbols = {reference.casefold(): item for reference, item in observed.component_symbols.items()}
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    grouped: dict[tuple[str, str], list[str]] = {}
    for reference, component in observed.components.items():
        reference_key = reference.casefold()
        symbol = symbols.get(reference_key)
        if (
            reference_key not in connector_references
            or reference_key in dnp_references
            or symbol is None
            or (component.part_id is not None and component.part_id.strip())
            or not component.value.strip()
            or not component.footprint.strip()
        ):
            continue
        identity = (component.footprint.strip().casefold(), component.value.strip().casefold())
        grouped.setdefault(identity, []).append(reference)

    candidate_groups = tuple(
        (identity, tuple(sorted(references, key=lambda item: (item.casefold(), item))))
        for identity, references in sorted(grouped.items())
        if len(references) >= 2
        and len({symbols[reference.casefold()].casefold() for reference in references}) >= 2
    )
    observed_pin_numbers = _observed_pin_numbers(observed)

    incomplete_inventory_count = 0
    incomplete_metadata_count = 0
    eligible_group_count = 0
    peer_scope_group_count = 0
    evaluated_pin_group_count = 0
    compared_pin_group_count = 0
    common_assignment_pin_group_count = 0
    different_assignment_pin_group_count = 0
    unassigned_assignment_pin_group_count = 0
    ambiguous_assignment_pin_group_count = 0
    generic_different_assignment_pin_group_count = 0
    non_generic_different_assignment_pin_group_count = 0
    common_anchor_group_count = 0
    unanchored_different_assignment_pin_group_count = 0
    open_peer_pin_group_count = 0
    unanchored_open_peer_pin_group_count = 0
    divergences: list[ConnectorFootprintPeerPinDivergence] = []
    open_outliers: list[ConnectorFootprintPeerPinOpenOutlier] = []

    for identity, peers in candidate_groups:
        folded_inventories = {
            reference.casefold(): tuple(
                number.casefold() for number in inventories.get(reference.casefold(), ())
            )
            for reference in peers
        }
        inventory_sets = {frozenset(numbers) for numbers in folded_inventories.values()}
        inventory_is_complete = (
            bool(inventory_sets)
            and all(folded_inventories.values())
            and all(len(set(numbers)) == len(numbers) for numbers in folded_inventories.values())
            and len(inventory_sets) == 1
            and all(
                observed_pin_numbers.get(reference.casefold(), set()).issubset(
                    set(folded_inventories[reference.casefold()])
                )
                for reference in peers
            )
        )
        if not inventory_is_complete:
            incomplete_inventory_count += 1
            continue

        folded_pin_numbers = next(iter(inventory_sets))
        display_pin_numbers = {
            folded: next(
                number for number in inventories[peers[0].casefold()] if number.casefold() == folded
            )
            for folded in sorted(folded_pin_numbers)
        }
        pin_numbers = tuple(display_pin_numbers.values())
        metadata_matches = all(
            all(
                (value := metadata.get(f"{reference}.{pin_number}".casefold())) is not None
                and value.strip()
                for reference in peers
            )
            and len(
                {
                    metadata[f"{reference}.{pin_number}".casefold()].strip().casefold()
                    for reference in peers
                }
            )
            == 1
            for pin_number in pin_numbers
            for metadata in (functions, electrical_types)
        )
        if not metadata_matches:
            incomplete_metadata_count += 1
            continue

        eligible_group_count += 1
        footprint_display = components[peers[0].casefold()].footprint.strip()
        value_display = components[peers[0].casefold()].value.strip()

        # Scope the peer set once. Assignment groups constrain comparison; they
        # do not establish that any two connector nets are required to match.
        representative_pin = pin_numbers[0]
        representative_assignments = {
            f"{reference}.{representative_pin}": () for reference in peers
        }
        scopes = tuple(
            (peer_group, scoped, basis)
            for peer_group, scoped, basis in partition_peer_assignments(
                representative_assignments,
                peer_assignment_groups,
            )
            if len(scoped) >= 2
        )

        for peer_group, scoped_assignments, basis in scopes:
            peer_scope_group_count += 1
            scope_references = tuple(
                sorted(
                    {pin.rsplit(".", 1)[0] for pin in scoped_assignments},
                    key=lambda item: (item.casefold(), item),
                )
            )
            anchors: list[str] = []
            generic_differences: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            generic_open_assignments: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            for pin_number in pin_numbers:
                assignments = {
                    f"{reference}.{pin_number}": tuple(
                        sorted(pin_nets.get(f"{reference}.{pin_number}".casefold(), ()))
                    )
                    for reference in scope_references
                }
                evaluated_pin_group_count += 1
                signatures = tuple(assignments.values())
                if any(len(signature) > 1 for signature in signatures):
                    ambiguous_assignment_pin_group_count += 1
                    continue
                if any(not signature for signature in signatures):
                    unassigned_assignment_pin_group_count += 1
                    assigned_signatures = tuple(signature for signature in signatures if signature)
                    function = functions[f"{scope_references[0]}.{pin_number}".casefold()]
                    if (
                        assigned_signatures
                        and len(set(assigned_signatures)) == 1
                        and not has_meaningful_pin_function(function)
                    ):
                        open_peer_pin_group_count += 1
                        generic_open_assignments.append((pin_number, assignments))
                    continue
                compared_pin_group_count += 1
                if len(set(signatures)) == 1:
                    common_assignment_pin_group_count += 1
                    anchors.append(pin_number)
                    continue

                different_assignment_pin_group_count += 1
                function = functions[f"{scope_references[0]}.{pin_number}".casefold()]
                if has_meaningful_pin_function(function):
                    non_generic_different_assignment_pin_group_count += 1
                else:
                    generic_different_assignment_pin_group_count += 1
                    generic_differences.append((pin_number, assignments))

            if anchors:
                common_anchor_group_count += 1
                peer_symbols = tuple(
                    sorted(
                        {symbols[reference.casefold()] for reference in scope_references},
                        key=lambda item: (item.casefold(), item),
                    )
                )
                for pin_number, assignments in generic_differences:
                    divergences.append(
                        ConnectorFootprintPeerPinDivergence(
                            footprint=footprint_display,
                            value=value_display,
                            pin_number=pin_number,
                            assignments=dict(sorted(assignments.items())),
                            symbols=peer_symbols,
                            common_anchor_pin_numbers=tuple(sorted(anchors)),
                            peer_assignment_group=peer_group,
                            peer_assignment_basis=basis,
                        )
                    )
                for pin_number, assignments in generic_open_assignments:
                    open_outliers.append(
                        ConnectorFootprintPeerPinOpenOutlier(
                            footprint=footprint_display,
                            value=value_display,
                            pin_number=pin_number,
                            assignments=dict(sorted(assignments.items())),
                            open_pins=tuple(pin for pin, nets in assignments.items() if not nets),
                            symbols=peer_symbols,
                            common_anchor_pin_numbers=tuple(sorted(anchors)),
                            peer_assignment_group=peer_group,
                            peer_assignment_basis=basis,
                        )
                    )
            else:
                unanchored_different_assignment_pin_group_count += len(generic_differences)
                unanchored_open_peer_pin_group_count += len(generic_open_assignments)

    divergences.sort(
        key=lambda item: (
            item.footprint.casefold(),
            item.value.casefold(),
            item.pin_number.casefold(),
            (item.peer_assignment_group or "").casefold(),
            tuple(pin.casefold() for pin in item.assignments),
        )
    )
    open_outliers.sort(
        key=lambda item: (
            item.footprint.casefold(),
            item.value.casefold(),
            item.pin_number.casefold(),
            (item.peer_assignment_group or "").casefold(),
            tuple(pin.casefold() for pin in item.assignments),
        )
    )
    return ConnectorFootprintPeerPinScan(
        candidate_group_count=len(candidate_groups),
        incomplete_pin_inventory_group_count=incomplete_inventory_count,
        incomplete_pin_metadata_group_count=incomplete_metadata_count,
        eligible_peer_group_count=eligible_group_count,
        peer_scope_group_count=peer_scope_group_count,
        evaluated_pin_group_count=evaluated_pin_group_count,
        compared_pin_group_count=compared_pin_group_count,
        common_assignment_pin_group_count=common_assignment_pin_group_count,
        different_assignment_pin_group_count=different_assignment_pin_group_count,
        unassigned_assignment_pin_group_count=unassigned_assignment_pin_group_count,
        ambiguous_assignment_pin_group_count=ambiguous_assignment_pin_group_count,
        generic_different_assignment_pin_group_count=(generic_different_assignment_pin_group_count),
        non_generic_different_assignment_pin_group_count=(
            non_generic_different_assignment_pin_group_count
        ),
        common_anchor_group_count=common_anchor_group_count,
        unanchored_different_assignment_pin_group_count=(
            unanchored_different_assignment_pin_group_count
        ),
        finding_count=len(divergences),
        open_peer_pin_group_count=open_peer_pin_group_count,
        unanchored_open_peer_pin_group_count=unanchored_open_peer_pin_group_count,
        open_outlier_finding_count=len(open_outliers),
        divergences=tuple(divergences),
        open_outliers=tuple(open_outliers),
    )
