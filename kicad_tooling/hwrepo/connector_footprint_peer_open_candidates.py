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
        if _is_reviewed_unanchored_open(item, current_scopes)
        and not _is_documented_intentional_open(item, mapped_pins)
    )
    return (*anchored, *unanchored)


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
