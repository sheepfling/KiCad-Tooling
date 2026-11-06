"""Revalidate generic unanchored connector contacts against their native scan."""

from __future__ import annotations

from .connector_comparison_scope_types import connector_comparison_scopes_by_reference
from .connector_footprint_peer_anchors import connector_footprint_peer_common_anchor_pin_numbers
from .connector_footprint_peer_assignments import (
    connector_footprint_peer_pin_assignments,
)
from .connector_footprint_peer_groups import (
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import native_pin_metadata_is_missing, pin_function_is_generic
from .netlist_pin_assignments import netlist_pin_net_index


def connector_footprint_peer_unanchored_references(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
) -> tuple[str, ...]:
    """Return the exact, stable peer references carried by one scan record."""
    return tuple(
        sorted(
            {pin.rsplit(".", 1)[0] for pin in item.assignments},
            key=lambda reference: (reference.casefold(), reference),
        )
    )


def connector_footprint_peer_unanchored_cohort_key(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    return (
        item.value.casefold(),
        item.footprint.casefold(),
        tuple(
            reference.casefold()
            for reference in connector_footprint_peer_unanchored_references(item)
        ),
        tuple(symbol.casefold() for symbol in item.symbols),
    )


def validate_current_unanchored_peer_contacts(
    *,
    scan: ConnectorFootprintPeerPinScan,
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...],
    partial_opens: tuple[ConnectorFootprintPeerPinOpenOutlier, ...],
    expected_peer_assignment_group: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Recheck one generic unanchored cohort against its current native source."""
    observed = scan.source.observed
    items = (*divergences, *partial_opens)
    if not items:
        raise ValueError("Unanchored peer evidence requires at least one contact")
    if any(item not in scan.unanchored_divergences for item in divergences) or any(
        item not in scan.unanchored_open_outliers for item in partial_opens
    ):
        raise ValueError("Unanchored peer contacts must come from the current native scan")
    if len({connector_footprint_peer_unanchored_cohort_key(item) for item in items}) != 1:
        raise ValueError("Unanchored peer evidence must contain one alias cohort")

    first = items[0]
    references = connector_footprint_peer_unanchored_references(first)
    source_peer_groups_by_reference = connector_comparison_scopes_by_reference(
        scan.source.peer_assignment_groups
    )
    if expected_peer_assignment_group is None:
        if any(reference.casefold() in source_peer_groups_by_reference for reference in references):
            raise ValueError(
                "Unanchored peer contacts must retain the absence of peer groups in their source scope"
            )
    elif not expected_peer_assignment_group.strip() or any(
        (scope := source_peer_groups_by_reference.get(reference.casefold())) is None
        or scope.group.casefold() != expected_peer_assignment_group.casefold()
        or not scope.basis.strip()
        for reference in references
    ):
        raise ValueError("Unanchored peer contacts must retain their current reviewed peer group")

    groups = connector_footprint_peer_candidate_groups(
        observed,
        scan.source.declared_references,
    )
    matching_groups = tuple(
        group
        for group in groups
        if group.value_key == first.value.casefold()
        and group.footprint_key == first.footprint.casefold()
        and {reference.casefold() for reference in references}.issubset(
            {reference.casefold() for reference in group.references}
        )
    )
    if len(matching_groups) != 1:
        raise ValueError("Unanchored peer identity must match current fitted aliases")
    group = matching_groups[0]
    inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
    if inventory is None:
        raise ValueError("Unanchored peer evidence requires a complete current pin inventory")

    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    current_symbols = tuple(
        sorted(
            {symbols[reference.casefold()] for reference in references},
            key=lambda item: (item.casefold(), item),
        )
    )
    if current_symbols != first.symbols:
        raise ValueError("Unanchored peer symbols must match the current native source")

    for pin_number in inventory.pin_numbers:
        function_values: list[str] = []
        electrical_values: list[str] = []
        for reference in group.references:
            display_number = inventory.displayed_numbers_by_reference[reference.casefold()][
                pin_number.casefold()
            ]
            pin = f"{reference}.{display_number}"
            function = functions.get(pin.casefold())
            electrical_type = electrical_types.get(pin.casefold())
            if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(
                electrical_type
            ):
                raise ValueError("Unanchored peer evidence requires complete native pin metadata")
            function_values.append(function or "")
            electrical_values.append(electrical_type or "")
        if (
            len({value.strip().casefold() for value in function_values}) != 1
            or len({value.strip().casefold() for value in electrical_values}) != 1
        ):
            raise ValueError("Unanchored peer metadata must still match across aliases")

    pin_nets = netlist_pin_net_index(observed)
    for item in items:
        scope_matches = (
            item.peer_assignment_group is None
            if expected_peer_assignment_group is None
            else item.peer_assignment_group is not None
            and item.peer_assignment_group.casefold() == expected_peer_assignment_group.casefold()
            and bool(item.peer_assignment_basis)
        )
        if (
            not scope_matches
            or item.common_anchor_pin_numbers
            or not pin_function_is_generic(item.pin_function)
            or item.pin_number.casefold()
            not in {number.casefold() for number in inventory.pin_numbers}
            or len(item.assignments) < 2
        ):
            raise ValueError("Unanchored peer contacts must remain generic and unscoped")
        expected_assignments: dict[str, tuple[str, ...]] = {}
        for reference in references:
            display_number = inventory.displayed_numbers_by_reference[reference.casefold()][
                item.pin_number.casefold()
            ]
            pin = f"{reference}.{display_number}"
            expected_assignments[pin] = connector_footprint_peer_pin_assignments(pin_nets, pin)
        if dict(item.assignments) != expected_assignments:
            raise ValueError("Unanchored peer assignments must match the current netlist")
        target_pin = (
            f"{references[0]}."
            f"{inventory.displayed_numbers_by_reference[references[0].casefold()][item.pin_number.casefold()]}"
        )
        if item.pin_function != functions.get(target_pin.casefold()):
            raise ValueError("Unanchored peer pin function must match the current netlist")

        assignments = tuple(item.assignments.values())
        if isinstance(item, ConnectorFootprintPeerPinDivergence):
            if (
                any(len(nets) != 1 for nets in assignments)
                or len({nets[0] for nets in assignments}) < 2
            ):
                raise ValueError("Unanchored split contacts require distinct exact net assignments")
        else:
            assigned = tuple(nets for nets in assignments if nets)
            target_type = electrical_types.get(target_pin.casefold())
            if (
                any(len(nets) > 1 for nets in assignments)
                or not any(not nets for nets in assignments)
                or not assigned
                or native_pin_metadata_is_missing(target_type)
                or (target_type or "").strip().casefold()
                not in {"passive", *SIGNAL_ELECTRICAL_TYPES}
            ):
                raise ValueError(
                    "Unanchored partial opens require one exact assigned net and an open peer"
                )

        anchors = connector_footprint_peer_common_anchor_pin_numbers(
            inventory.pin_numbers,
            item.pin_number,
            references,
            inventory.displayed_numbers_by_reference,
            pin_nets,
        )
        if anchors:
            raise ValueError("Unanchored peer contacts must have no current common anchor")

    return references, group.references
