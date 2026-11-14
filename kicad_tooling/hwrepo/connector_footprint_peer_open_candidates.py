"""Review generic partial-open contacts across footprint-alias connectors."""

from __future__ import annotations

from .connector_comparison_scope_types import (
    ConnectorComparisonScopes,
    connector_comparison_scopes_by_reference,
)
from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidenceByComponentPin,
)
from .connector_footprint_peer_all_open import GENERIC_ALL_OPEN_PIN_TYPES, GENERIC_POWER_PIN_TYPES
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import partition_peer_assignments, pin_function_is_generic
from .design_lint_connector_footprint_candidate_evidence import (
    ConnectorFootprintPeerPinCandidate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def footprint_peer_pin_open_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review anchored and explicitly scoped unanchored generic partial opens."""
    anchored = tuple(
        _candidate(item, anchored=True)
        for item in scan.open_outliers
        if pin_function_is_generic(item.pin_function)
        and item.pin_electrical_type.strip().casefold() in GENERIC_ALL_OPEN_PIN_TYPES
    )
    current_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    scan_scopes = scan.source.peer_assignment_groups
    if connector_comparison_scopes_by_reference(current_scopes) != (
        connector_comparison_scopes_by_reference(scan_scopes)
    ):
        return anchored

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    unanchored = tuple(
        _candidate(item, anchored=False)
        for item in scan.unanchored_open_outliers
        if item.pin_electrical_type.strip().casefold() in GENERIC_ALL_OPEN_PIN_TYPES
        and _is_reviewed_unanchored_open(item, current_scopes)
        and not _is_documented_intentional_open(item, mapped_pins)
    )
    return (*anchored, *unanchored)


def footprint_peer_generic_power_open_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review partial-open generic power contacts across exact footprint peers."""
    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    anchored = tuple(
        _power_candidate(item, anchored=True)
        for item in scan.open_outliers
        if _is_generic_power_contact(item) and _has_one_assigned_net(item)
    )
    current_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    scan_scopes = scan.source.peer_assignment_groups
    if connector_comparison_scopes_by_reference(current_scopes) != (
        connector_comparison_scopes_by_reference(scan_scopes)
    ):
        return anchored

    unanchored = tuple(
        _power_candidate(item, anchored=False)
        for item in scan.unanchored_open_outliers
        if _is_generic_power_contact(item)
        and _is_reviewed_unanchored_open(item, current_scopes)
        and not _is_documented_intentional_open(item, mapped_pins)
    )
    return (*anchored, *unanchored)


def _is_generic_power_contact(item: ConnectorFootprintPeerPinOpenOutlier) -> bool:
    return (
        pin_function_is_generic(item.pin_function)
        and item.pin_electrical_type.strip().casefold() in GENERIC_POWER_PIN_TYPES
    )


def _has_one_assigned_net(item: ConnectorFootprintPeerPinOpenOutlier) -> bool:
    if (
        len(item.assignments) < 2
        or not any(not nets for nets in item.assignments.values())
        or any(len(nets) > 1 for nets in item.assignments.values())
    ):
        return False
    return len({nets[0] for nets in item.assignments.values() if nets}) == 1


def _is_reviewed_unanchored_open(
    item: ConnectorFootprintPeerPinOpenOutlier,
    current_scopes: ConnectorComparisonScopes,
) -> bool:
    """Require one current peer group, generic pin evidence, and one assigned net."""
    if (
        not pin_function_is_generic(item.pin_function)
        or item.common_anchor_pin_numbers
        or not item.peer_assignment_group
        or not item.peer_assignment_basis
        or len(item.assignments) < 2
        or any(len(nets) > 1 for nets in item.assignments.values())
        or not any(not nets for nets in item.assignments.values())
    ):
        return False
    assigned_nets = {nets[0] for nets in item.assignments.values() if nets}
    if len(assigned_nets) != 1:
        return False

    partitions = partition_peer_assignments(
        item.assignments,
        connector_comparison_scopes_by_reference(current_scopes),
    )
    return (
        len(partitions) == 1
        and partitions[0].peer_assignment_group == item.peer_assignment_group
        and partitions[0].peer_assignment_basis == item.peer_assignment_basis
        and dict(partitions[0].assignments_by_pin) == dict(item.assignments)
    )


def _is_documented_intentional_open(
    item: ConnectorFootprintPeerPinOpenOutlier,
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
) -> bool:
    """Suppress only when every open pin has current explicit no-connect evidence."""
    return bool(item.open_pins) and all(
        (mapped := mapped_pins.get(pin)) is not None
        and mapped.unconnected_reason is not None
        and not mapped.nets
        for pin in item.open_pins
    )


def _candidate(
    item: ConnectorFootprintPeerPinOpenOutlier,
    *,
    anchored: bool,
) -> Candidate:
    if anchored:
        message = (
            "Fitted connector instances with distinct native symbols share the same value, "
            "footprint, complete pin inventory, and matching pin-function and electrical-type "
            "metadata. This generic contact is assigned on some peers and unassigned on others, "
            "while a separate contact has one common assigned net. Review the approved pinout "
            "for an intentional open or a missing connection; similarity does not prove that "
            "this contact must connect."
        )
    else:
        message = (
            "Fitted connector instances with distinct native symbols share the same value, "
            "footprint, complete pin inventory, and matching pin-function and electrical-type "
            "metadata. This generic contact is assigned on some peers and unassigned on others "
            "without a common-net anchor. A current source-reviewed peer-assignment group scopes "
            "the comparison. Review the approved pinout for an intentional open or a missing "
            "connection; similarity and scope do not prove that this contact must connect."
        )
    if anchored and item.peer_assignment_group is not None:
        message += " The comparison is scoped to a source-reviewed peer-assignment group."
    return ConnectorFootprintPeerPinCandidate.from_source_evidence(
        item,
        subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
        message=message,
    )


def _power_candidate(
    item: ConnectorFootprintPeerPinOpenOutlier,
    *,
    anchored: bool,
) -> Candidate:
    """Project one generic power partial-open record as its dedicated rule."""
    if anchored:
        scope_message = " A separate contact has one common assigned net."
    else:
        scope_message = (
            " No common-net anchor exists; a current source-reviewed peer-assignment group "
            "scopes the comparison."
        )
    if item.peer_assignment_group is not None:
        scope_message += " The comparison is scoped to a source-reviewed peer group."
    return ConnectorFootprintPeerPinCandidate.from_source_evidence(
        item,
        subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
        message=(
            "Fitted footprint-similar connector aliases have a generic native power contact "
            "assigned on some peers and unassigned on others. Review the approved pinout and "
            "intended port use; the individual open-pin finding already reports the open pin, "
            "and peer similarity does not prove that this contact must connect." + scope_message
        ),
    )
