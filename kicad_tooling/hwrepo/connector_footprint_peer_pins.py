"""Conservative peer-pin review across connector symbol aliases without PART_ID."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_peer_groups import (
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinAllOpen,
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinNamedAllOpen,
    ConnectorFootprintPeerPinNamedDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    native_pin_metadata_is_missing,
    partition_peer_assignments,
    pin_function_is_generic,
)
from .models import NetlistContract

_GENERIC_ALL_OPEN_PIN_TYPES = frozenset(
    {
        "passive",
        "input",
        "output",
        "bidirectional",
        "tri_state",
        "open_collector",
        "open_emitter",
    }
)


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
    symbols = {reference.casefold(): item for reference, item in observed.component_symbols.items()}
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    candidate_groups = connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
    )

    incomplete_inventory_count = 0
    incomplete_metadata_count = 0
    differing_metadata_count = 0
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
    all_open_peer_pin_group_count = 0
    unanchored_all_open_peer_pin_group_count = 0
    divergences: list[ConnectorFootprintPeerPinDivergence] = []
    named_divergences: list[ConnectorFootprintPeerPinNamedDivergence] = []
    open_outliers: list[ConnectorFootprintPeerPinOpenOutlier] = []
    all_open: list[ConnectorFootprintPeerPinAllOpen] = []
    named_all_open: list[ConnectorFootprintPeerPinNamedAllOpen] = []

    for group in candidate_groups:
        peers = group.references
        inventory = complete_connector_footprint_peer_pin_inventory(observed, peers)
        if inventory is None:
            incomplete_inventory_count += 1
            continue
        pin_numbers, display_pin_numbers = inventory
        metadata_values_by_field = tuple(
            tuple(
                metadata.get(
                    f"{reference}.{display_pin_numbers[reference.casefold()][pin_number.casefold()]}".casefold()
                )
                for reference in peers
            )
            for pin_number in pin_numbers
            for metadata in (functions, electrical_types)
        )
        metadata_complete = all(
            not native_pin_metadata_is_missing(value)
            for values in metadata_values_by_field
            for value in values
        )
        if not metadata_complete:
            incomplete_metadata_count += 1
            continue
        metadata_matches = all(
            len({value.strip().casefold() for value in values if value is not None}) == 1
            for values in metadata_values_by_field
        )
        if not metadata_matches:
            differing_metadata_count += 1
            continue

        eligible_group_count += 1
        footprint_display = group.footprint
        value_display = group.value

        # Scope the peer set once. Assignment groups constrain comparison; they
        # do not establish that any two connector nets are required to match.
        representative_pin = pin_numbers[0]
        representative_assignments = {
            f"{reference}.{display_pin_numbers[reference.casefold()][representative_pin.casefold()]}": ()
            for reference in peers
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
            named_differences: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            generic_open_assignments: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            named_open_assignments: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            generic_all_open_assignments: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            named_all_open_assignments: list[tuple[str, dict[str, tuple[str, ...]]]] = []
            for pin_number in pin_numbers:
                assignments = {
                    f"{reference}.{display_pin_numbers[reference.casefold()][pin_number.casefold()]}": tuple(
                        sorted(
                            pin_nets.get(
                                f"{reference}.{display_pin_numbers[reference.casefold()][pin_number.casefold()]}".casefold(),
                                (),
                            )
                        )
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
                    pin_type = (
                        electrical_types[f"{scope_references[0]}.{pin_number}".casefold()]
                        .strip()
                        .casefold()
                    )
                    if not assigned_signatures and (
                        pin_type in _GENERIC_ALL_OPEN_PIN_TYPES
                        and pin_function_is_generic(function)
                    ):
                        all_open_peer_pin_group_count += 1
                        generic_all_open_assignments.append((pin_number, assignments))
                    elif (
                        not assigned_signatures
                        and pin_type in {"power_in", "power_out"} | SIGNAL_ELECTRICAL_TYPES
                        and not pin_function_is_generic(function)
                        and not is_named_supply_function(function)
                        and not is_return_function(function)
                    ):
                        named_all_open_assignments.append((pin_number, assignments))
                    elif assigned_signatures and len(set(assigned_signatures)) == 1:
                        target_pin = f"{scope_references[0]}.{pin_number}"
                        pin_type = electrical_types[target_pin.casefold()].strip().casefold()
                        if pin_function_is_generic(function):
                            open_peer_pin_group_count += 1
                            generic_open_assignments.append((pin_number, assignments))
                        elif (
                            pin_type
                            in {"passive", "power_in", "power_out"} | SIGNAL_ELECTRICAL_TYPES
                            and not is_named_supply_function(function)
                            and not is_return_function(function)
                        ):
                            open_peer_pin_group_count += 1
                            named_open_assignments.append((pin_number, assignments))
                    continue
                compared_pin_group_count += 1
                if len(set(signatures)) == 1:
                    common_assignment_pin_group_count += 1
                    anchors.append(pin_number)
                    continue

                different_assignment_pin_group_count += 1
                function = functions[f"{scope_references[0]}.{pin_number}".casefold()]
                if pin_function_is_generic(function):
                    generic_different_assignment_pin_group_count += 1
                    generic_differences.append((pin_number, assignments))
                else:
                    non_generic_different_assignment_pin_group_count += 1
                    named_differences.append((pin_number, assignments))

            peer_symbols = tuple(
                sorted(
                    {symbols[reference.casefold()] for reference in scope_references},
                    key=lambda item: (item.casefold(), item),
                )
            )
            for pin_number, assignments in named_differences:
                named_divergences.append(
                    ConnectorFootprintPeerPinNamedDivergence(
                        footprint=footprint_display,
                        value=value_display,
                        pin_number=pin_number,
                        pin_function=functions[f"{scope_references[0]}.{pin_number}".casefold()],
                        pin_electrical_type=electrical_types[
                            f"{scope_references[0]}.{pin_number}".casefold()
                        ],
                        assignments=dict(sorted(assignments.items())),
                        symbols=peer_symbols,
                        common_anchor_pin_numbers=tuple(sorted(anchors)),
                        peer_assignment_group=peer_group,
                        peer_assignment_basis=basis,
                    )
                )
            if anchors:
                common_anchor_group_count += 1
                for pin_number, assignments in generic_differences:
                    divergences.append(
                        ConnectorFootprintPeerPinDivergence(
                            footprint=footprint_display,
                            value=value_display,
                            pin_number=pin_number,
                            pin_function=functions[
                                f"{scope_references[0]}.{pin_number}".casefold()
                            ],
                            assignments=dict(sorted(assignments.items())),
                            symbols=peer_symbols,
                            common_anchor_pin_numbers=tuple(sorted(anchors)),
                            peer_assignment_group=peer_group,
                            peer_assignment_basis=basis,
                        )
                    )
                for pin_number, assignments in named_open_assignments:
                    named_power_input_open_outlier = ConnectorFootprintPeerPinOpenOutlier(
                        footprint=footprint_display,
                        value=value_display,
                        pin_number=pin_number,
                        pin_function=functions[f"{scope_references[0]}.{pin_number}".casefold()],
                        pin_electrical_type=electrical_types[
                            f"{scope_references[0]}.{pin_number}".casefold()
                        ],
                        assignments=dict(sorted(assignments.items())),
                        open_pins=tuple(pin for pin, nets in assignments.items() if not nets),
                        symbols=peer_symbols,
                        common_anchor_pin_numbers=tuple(sorted(anchors)),
                        peer_assignment_group=peer_group,
                        peer_assignment_basis=basis,
                    )
                    open_outliers.append(named_power_input_open_outlier)
                for pin_number, assignments in generic_open_assignments:
                    open_outliers.append(
                        ConnectorFootprintPeerPinOpenOutlier(
                            footprint=footprint_display,
                            value=value_display,
                            pin_number=pin_number,
                            pin_function=functions[
                                f"{scope_references[0]}.{pin_number}".casefold()
                            ],
                            pin_electrical_type=electrical_types[
                                f"{scope_references[0]}.{pin_number}".casefold()
                            ],
                            assignments=dict(sorted(assignments.items())),
                            open_pins=tuple(pin for pin, nets in assignments.items() if not nets),
                            symbols=peer_symbols,
                            common_anchor_pin_numbers=tuple(sorted(anchors)),
                            peer_assignment_group=peer_group,
                            peer_assignment_basis=basis,
                        )
                    )
                for pin_number, assignments in generic_all_open_assignments:
                    all_open.append(
                        ConnectorFootprintPeerPinAllOpen(
                            footprint=footprint_display,
                            value=value_display,
                            pin_number=pin_number,
                            pin_function=functions[
                                f"{scope_references[0]}.{pin_number}".casefold()
                            ],
                            assignments=dict(sorted(assignments.items())),
                            symbols=peer_symbols,
                            common_anchor_pin_numbers=tuple(sorted(anchors)),
                            peer_assignment_group=peer_group,
                            peer_assignment_basis=basis,
                        )
                    )
            else:
                unanchored_different_assignment_pin_group_count += len(generic_differences)
                unanchored_open_peer_pin_group_count += len(generic_open_assignments) + len(
                    named_open_assignments
                )
                unanchored_all_open_peer_pin_group_count += len(generic_all_open_assignments)
            for pin_number, assignments in named_all_open_assignments:
                named_all_open.append(
                    ConnectorFootprintPeerPinNamedAllOpen(
                        footprint=footprint_display,
                        value=value_display,
                        pin_number=pin_number,
                        pin_function=functions[f"{scope_references[0]}.{pin_number}".casefold()],
                        pin_electrical_type=electrical_types[
                            f"{scope_references[0]}.{pin_number}".casefold()
                        ],
                        assignments=dict(sorted(assignments.items())),
                        symbols=peer_symbols,
                        common_anchor_pin_numbers=tuple(sorted(anchors)),
                        peer_assignment_group=peer_group,
                        peer_assignment_basis=basis,
                    )
                )

    divergences.sort(
        key=lambda item: (
            item.footprint.casefold(),
            item.value.casefold(),
            item.pin_number.casefold(),
            (item.peer_assignment_group or "").casefold(),
            tuple(pin.casefold() for pin in item.assignments),
        )
    )
    named_divergences.sort(
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
    all_open.sort(
        key=lambda item: (
            item.footprint.casefold(),
            item.value.casefold(),
            item.pin_number.casefold(),
            (item.peer_assignment_group or "").casefold(),
            tuple(pin.casefold() for pin in item.assignments),
        )
    )
    named_all_open.sort(
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
        differing_pin_metadata_group_count=differing_metadata_count,
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
        all_open_peer_pin_group_count=all_open_peer_pin_group_count,
        unanchored_all_open_peer_pin_group_count=unanchored_all_open_peer_pin_group_count,
        all_open_finding_count=len(all_open),
        divergences=tuple(divergences),
        named_divergences=tuple(named_divergences),
        open_outliers=tuple(open_outliers),
        all_open=tuple(all_open),
        named_all_open=tuple(named_all_open),
    )
