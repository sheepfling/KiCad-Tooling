"""Review numeric-only connector contacts open on one exact-symbol peer."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from typing import Literal

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_coverage_models import ConnectorMappedPinEvidenceByComponentPin
from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerPinInventory,
    complete_connector_footprint_peer_pin_inventory,
)
from .connector_identity import connector_candidate_references, partition_peer_assignments
from .connector_numeric_peer_open_evidence import (
    CONNECTOR_PEER_NUMERIC_SIGNAL_TYPES,
    ConnectorNumericPeerAnchor,
    ConnectorNumericPeerOpenCandidate,
    ConnectorNumericPeerOpenEvidence,
    complete_connector_numeric_peer_pin_metadata,
)
from .connector_peer_pin_scan import scan_connector_part_id_peer_pins
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


def _shared_anchors(
    pin_index: Mapping[str, AbstractSet[str]],
    inventory: ConnectorFootprintPeerPinInventory,
    references: tuple[str, ...],
    target_pin_number: str,
) -> tuple[ConnectorNumericPeerAnchor, ...]:
    displayed = inventory.displayed_numbers_by_reference
    anchors: list[ConnectorNumericPeerAnchor] = []
    for number in inventory.pin_numbers:
        if number.casefold() == target_pin_number.casefold():
            continue
        pins = tuple(
            f"{reference}.{displayed[reference.casefold()][number.casefold()]}"
            for reference in references
        )
        nets_by_peer = tuple(pin_index.get(pin.casefold(), frozenset()) for pin in pins)
        if (
            nets_by_peer
            and all(len(nets) == 1 for nets in nets_by_peer)
            and len({next(iter(nets)) for nets in nets_by_peer}) == 1
        ):
            anchors.append(
                ConnectorNumericPeerAnchor(
                    pin_number=number,
                    pins=pins,
                    net=next(iter(nets_by_peer[0])),
                )
            )
    return tuple(sorted(anchors, key=lambda item: (item.pin_number.casefold(), item.pin_number)))


def _candidate_for_peer_scope(
    observed: NetlistContract,
    *,
    symbol: str,
    pin_number: str,
    electrical_type: str,
    assignments: Mapping[str, tuple[str, ...]],
    pin_metadata: Mapping[str, tuple[str, str]],
    anchors: tuple[ConnectorNumericPeerAnchor, ...],
    peer_assignment_group: str | None = None,
    peer_assignment_basis: tuple[str, ...] = (),
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol",
    peer_identity: str = "",
    peer_symbols: tuple[str, ...] = (),
) -> ConnectorNumericPeerOpenCandidate:
    """Build one candidate from a fully scoped and validated peer comparison."""
    source = ConnectorNumericPeerOpenEvidence(
        observed=observed,
        symbol=symbol,
        pin_number=pin_number,
        electrical_type=electrical_type,
        assignments=assignments,
        pin_metadata=pin_metadata,
        shared_anchors=anchors,
        peer_assignment_group=peer_assignment_group,
        peer_assignment_basis=peer_assignment_basis,
        peer_identity_basis=peer_identity_basis,
        peer_identity=peer_identity,
        peer_symbols=peer_symbols,
    )
    open_references = tuple(pin.rpartition(".")[0] for pin, nets in assignments.items() if not nets)
    assigned_net = next(nets[0] for nets in assignments.values() if nets)
    peer_description = (
        f"PART_ID {peer_identity} aliases"
        if peer_identity_basis == "part_id"
        else "exact-symbol peers"
    )
    return ConnectorNumericPeerOpenCandidate.from_source_evidence(
        source,
        subject=(
            f"{peer_description} pin {pin_number}: generic contact is open on "
            f"{', '.join(open_references)}"
        ),
        message=(
            "This numeric-only connector contact is unassigned on one or more fitted "
            f"{peer_description} while assigned peers use {assigned_net}. Another contact "
            "supplies a shared schematic-net anchor. Review the approved pinout for an "
            "intentional open, per-port isolation, or a missing connection; these similarity "
            "and assignment clues do not establish that this contact must connect."
            + (
                " The comparison is scoped by a source-reviewed peer-assignment group."
                if peer_assignment_group is not None
                else ""
            )
        ),
    )


def generic_numeric_connector_peer_pin_open_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: ConnectorMappedPinEvidenceByComponentPin | None = None,
    peer_assignment_groups: ConnectorComparisonScopes | None = None,
    not_applicable_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review an open numeric-only contact beside comparable connector peers.

    A complete matching pin inventory and function/type metadata are required.
    Peers may share an exact symbol or a guarded PART_ID across different
    symbols; the latter also requires matching value and footprint metadata.
    Every assigned peer must use the same one exact net, a current
    source-matched pin map suppresses the prompt, and a different pin must
    anchor the comparison to one common exact net. Native netlist evidence
    represents ordinary opens and explicit no-connects alike, so either can
    prompt. None of these clues declares that the open contact should connect.
    """
    mapped_pin_keys = {pin.casefold() for pin in reviewed_connector_pins or {}}
    excluded_references = {reference.casefold() for reference in not_applicable_references}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    candidate_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    } - excluded_references
    symbols = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    references_by_symbol: dict[str, list[str]] = {}
    for reference_key, (reference, symbol) in symbols.items():
        if reference_key in candidate_references and reference_key not in dnp_references:
            references_by_symbol.setdefault(symbol.casefold(), []).append(reference)

    pin_index = netlist_pin_net_index(observed)
    exact_candidates: list[ConnectorNumericPeerOpenCandidate] = []
    for peer_symbols in references_by_symbol.values():
        references = tuple(sorted(peer_symbols, key=lambda item: (item.casefold(), item)))
        if len(references) < 2:
            continue
        inventory = complete_connector_footprint_peer_pin_inventory(observed, references)
        if inventory is None:
            continue
        pin_metadata = complete_connector_numeric_peer_pin_metadata(observed, inventory, references)
        if pin_metadata is None:
            continue
        metadata_by_pin = {pin.casefold(): values for pin, values in pin_metadata.items()}
        symbol = symbols[references[0].casefold()][1]

        for pin_number in inventory.pin_numbers:
            target_pins = tuple(
                f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}"
                for reference in references
            )
            target_metadata = tuple(metadata_by_pin[pin.casefold()] for pin in target_pins)
            target_functions = {function.strip() for function, _ in target_metadata}
            target_types = {
                electrical_type.strip().casefold() for _, electrical_type in target_metadata
            }
            if (
                len(target_functions) != 1
                or re.fullmatch(r"[0-9]+", next(iter(target_functions), "")) is None
                or len(target_types) != 1
                or next(iter(target_types), "") not in CONNECTOR_PEER_NUMERIC_SIGNAL_TYPES
            ):
                continue
            electrical_type = next(iter(target_types))
            all_assignments = {
                pin: tuple(
                    sorted(
                        pin_index.get(pin.casefold(), frozenset()),
                        key=lambda net: (net.casefold(), net),
                    )
                )
                for pin in target_pins
            }
            for partition in partition_peer_assignments(all_assignments, peer_assignment_groups):
                assignments = partition.assignments_by_pin
                scoped_references = tuple(
                    sorted(
                        {pin.rpartition(".")[0] for pin in assignments},
                        key=lambda item: (item.casefold(), item),
                    )
                )
                signatures = tuple(assignments.values())
                if (
                    len(scoped_references) < 2
                    or not any(not nets for nets in signatures)
                    or not any(nets for nets in signatures)
                    or any(len(nets) > 1 for nets in signatures)
                    or len({nets for nets in signatures if nets}) != 1
                    or any(pin.casefold() in mapped_pin_keys for pin in assignments)
                ):
                    continue
                anchors = _shared_anchors(
                    pin_index,
                    inventory,
                    scoped_references,
                    pin_number,
                )
                if not anchors:
                    continue
                scoped_pin_metadata = {
                    pin: pin_metadata[pin]
                    for reference in scoped_references
                    for number in inventory.pin_numbers
                    for pin in (
                        f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][number.casefold()]}",
                    )
                }
                exact_candidates.append(
                    _candidate_for_peer_scope(
                        observed,
                        symbol=symbol,
                        pin_number=pin_number,
                        electrical_type=electrical_type,
                        assignments=assignments,
                        pin_metadata=scoped_pin_metadata,
                        anchors=anchors,
                        peer_assignment_group=partition.peer_assignment_group,
                        peer_assignment_basis=partition.peer_assignment_basis,
                    )
                )
    part_id_candidates: list[ConnectorNumericPeerOpenCandidate] = []
    part_id_scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    for group in part_id_scan.pin_groups:
        assignments = dict(group.assignments)
        references = tuple(
            sorted(
                {pin.rpartition(".")[0] for pin in assignments},
                key=lambda item: (item.casefold(), item),
            )
        )
        scoped_symbols = tuple(
            sorted(
                {
                    observed.component_symbols[reference]
                    for reference in references
                    if reference in observed.component_symbols
                },
                key=lambda item: (item.casefold(), item),
            )
        )
        if (
            len(references) < 2
            or len(scoped_symbols) < 2
            or any(reference.casefold() in excluded_references for reference in references)
            or group.pin_electrical_type.strip().casefold()
            not in CONNECTOR_PEER_NUMERIC_SIGNAL_TYPES
            or re.fullmatch(r"[0-9]+", group.pin_function.strip()) is None
            or not any(not nets for nets in assignments.values())
            or not any(nets for nets in assignments.values())
            or any(len(nets) > 1 for nets in assignments.values())
            or len({nets for nets in assignments.values() if nets}) != 1
            or any(pin.casefold() in mapped_pin_keys for pin in assignments)
        ):
            continue
        inventory = complete_connector_footprint_peer_pin_inventory(observed, references)
        if inventory is None:
            continue
        pin_metadata = complete_connector_numeric_peer_pin_metadata(observed, inventory, references)
        if pin_metadata is None:
            continue
        anchors = _shared_anchors(pin_index, inventory, references, group.pin_number)
        if not anchors:
            continue
        part_id_candidates.append(
            _candidate_for_peer_scope(
                observed,
                symbol="multiple connector symbols",
                pin_number=group.pin_number,
                electrical_type=group.pin_electrical_type,
                assignments=assignments,
                pin_metadata=pin_metadata,
                anchors=anchors,
                peer_assignment_group=group.peer_assignment_group,
                peer_assignment_basis=group.peer_assignment_basis,
                peer_identity_basis="part_id",
                peer_identity=group.part_id,
                peer_symbols=scoped_symbols,
            )
        )

    def is_subsumed_by_part_id(exact: ConnectorNumericPeerOpenCandidate) -> bool:
        exact_source = exact.source_evidence
        exact_assignments = {pin.casefold(): nets for pin, nets in exact_source.assignments.items()}
        exact_open_pins = {
            pin.casefold() for pin, nets in exact_source.assignments.items() if not nets
        }
        for alias in part_id_candidates:
            alias_source = alias.source_evidence
            if exact_source.pin_number.casefold() != alias_source.pin_number.casefold():
                continue
            alias_assignments = {
                pin.casefold(): nets for pin, nets in alias_source.assignments.items()
            }
            alias_open_pins = {
                pin.casefold() for pin, nets in alias_source.assignments.items() if not nets
            }
            if (
                exact_assignments.keys() <= alias_assignments.keys()
                and all(alias_assignments[pin] == nets for pin, nets in exact_assignments.items())
                and exact_open_pins <= alias_open_pins
            ):
                return True
        return False

    candidates = (
        *part_id_candidates,
        *(item for item in exact_candidates if not is_subsumed_by_part_id(item)),
    )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )
