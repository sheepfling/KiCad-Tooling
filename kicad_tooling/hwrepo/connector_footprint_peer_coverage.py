"""Assemble source-bound coverage for connector footprint aliases."""

from __future__ import annotations

from typing import Protocol

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_peer_pin_models import ConnectorFootprintPeerPinCoverage


class _NamedCoverageEvaluation(Protocol):
    @property
    def candidate_count(self) -> int: ...

    @property
    def unanchored_count(self) -> int: ...


def build_connector_footprint_peer_pin_coverage(
    scan: ConnectorFootprintPeerPinScan,
    netlist_sha256: str,
    *,
    generic_divergence_finding_count: int,
    open_outlier_finding_count: int,
    all_open_finding_count: int,
    named_signal_divergence: _NamedCoverageEvaluation,
    named_signal_divergence_finding_count: int,
    named_power_input_divergence: _NamedCoverageEvaluation,
    named_power_input_divergence_finding_count: int,
    named_power_input_all_open: _NamedCoverageEvaluation,
    named_power_input_all_open_finding_count: int,
    named_power_output_all_open: _NamedCoverageEvaluation,
    named_power_output_all_open_finding_count: int,
    named_signal_all_open: _NamedCoverageEvaluation,
    named_signal_all_open_finding_count: int,
    named_power_output_divergence: _NamedCoverageEvaluation,
    named_power_output_divergence_finding_count: int,
    named_passive_divergence: _NamedCoverageEvaluation,
    named_passive_divergence_finding_count: int,
) -> ConnectorFootprintPeerPinCoverage:
    """Build validated coverage counts and status for one footprint-alias scan."""
    incomplete_count = sum(
        (
            scan.incomplete_pin_inventory_group_count,
            scan.incomplete_pin_metadata_group_count,
            scan.unassigned_assignment_pin_group_count,
            scan.ambiguous_assignment_pin_group_count,
        )
    )
    status = (
        "NO_CANDIDATES"
        if scan.candidate_group_count == 0
        else "INCOMPLETE_EVIDENCE"
        if scan.eligible_peer_group_count == 0 and scan.differing_pin_metadata_group_count == 0
        else "PARTIALLY_EVALUATED"
        if scan.differing_pin_metadata_group_count > 0
        else "NO_PEER_SCOPES"
        if scan.peer_scope_group_count == 0
        else "NO_COMPARABLE_ASSIGNMENTS"
        if scan.evaluated_pin_group_count == 0
        else "NO_SHARED_ASSIGNMENT_ANCHOR"
        if scan.common_anchor_group_count == 0
        else "PARTIALLY_EVALUATED"
        if incomplete_count > 0
        else "NO_DIVERGENT_ASSIGNMENTS"
        if (
            scan.generic_different_assignment_pin_group_count
            + named_signal_divergence.candidate_count
            + named_power_input_divergence.candidate_count
            + named_power_output_divergence.candidate_count
            + named_passive_divergence.candidate_count
            == 0
        )
        else "EVALUATED"
    )
    return ConnectorFootprintPeerPinCoverage(
        status=status,
        netlist_sha256=netlist_sha256,
        candidate_group_count=scan.candidate_group_count,
        incomplete_pin_inventory_group_count=scan.incomplete_pin_inventory_group_count,
        incomplete_pin_metadata_group_count=scan.incomplete_pin_metadata_group_count,
        differing_pin_metadata_group_count=scan.differing_pin_metadata_group_count,
        eligible_peer_group_count=scan.eligible_peer_group_count,
        peer_scope_group_count=scan.peer_scope_group_count,
        evaluated_pin_group_count=scan.evaluated_pin_group_count,
        compared_pin_group_count=scan.compared_pin_group_count,
        common_assignment_pin_group_count=scan.common_assignment_pin_group_count,
        different_assignment_pin_group_count=scan.different_assignment_pin_group_count,
        unassigned_assignment_pin_group_count=scan.unassigned_assignment_pin_group_count,
        ambiguous_assignment_pin_group_count=scan.ambiguous_assignment_pin_group_count,
        generic_different_assignment_pin_group_count=(
            scan.generic_different_assignment_pin_group_count
        ),
        non_generic_different_assignment_pin_group_count=(
            scan.non_generic_different_assignment_pin_group_count
        ),
        common_anchor_group_count=scan.common_anchor_group_count,
        unanchored_different_assignment_pin_group_count=(
            scan.unanchored_different_assignment_pin_group_count
        ),
        divergence_finding_count=generic_divergence_finding_count,
        open_peer_pin_group_count=scan.open_peer_pin_group_count,
        unanchored_open_peer_pin_group_count=scan.unanchored_open_peer_pin_group_count,
        open_outlier_finding_count=open_outlier_finding_count,
        all_open_peer_pin_group_count=scan.all_open_peer_pin_group_count,
        unanchored_all_open_peer_pin_group_count=scan.unanchored_all_open_peer_pin_group_count,
        all_open_finding_count=all_open_finding_count,
        named_signal_different_assignment_pin_group_count=(named_signal_divergence.candidate_count),
        unanchored_named_signal_divergence_pin_group_count=(
            named_signal_divergence.unanchored_count
        ),
        named_signal_divergence_finding_count=named_signal_divergence_finding_count,
        named_power_input_different_assignment_pin_group_count=(
            named_power_input_divergence.candidate_count
        ),
        unanchored_named_power_input_divergence_pin_group_count=(
            named_power_input_divergence.unanchored_count
        ),
        named_power_input_divergence_finding_count=named_power_input_divergence_finding_count,
        named_power_input_all_open_peer_pin_group_count=named_power_input_all_open.candidate_count,
        unanchored_named_power_input_all_open_peer_pin_group_count=(
            named_power_input_all_open.unanchored_count
        ),
        named_power_input_all_open_finding_count=named_power_input_all_open_finding_count,
        named_power_output_all_open_peer_pin_group_count=named_power_output_all_open.candidate_count,
        unanchored_named_power_output_all_open_peer_pin_group_count=(
            named_power_output_all_open.unanchored_count
        ),
        named_power_output_all_open_finding_count=named_power_output_all_open_finding_count,
        named_signal_all_open_peer_pin_group_count=named_signal_all_open.candidate_count,
        unanchored_named_signal_all_open_peer_pin_group_count=(
            named_signal_all_open.unanchored_count
        ),
        named_signal_all_open_finding_count=named_signal_all_open_finding_count,
        named_power_output_different_assignment_pin_group_count=(
            named_power_output_divergence.candidate_count
        ),
        unanchored_named_power_output_divergence_pin_group_count=(
            named_power_output_divergence.unanchored_count
        ),
        named_power_output_divergence_finding_count=named_power_output_divergence_finding_count,
        named_passive_different_assignment_pin_group_count=(
            named_passive_divergence.candidate_count
        ),
        unanchored_named_passive_divergence_pin_group_count=(
            named_passive_divergence.unanchored_count
        ),
        named_passive_divergence_finding_count=named_passive_divergence_finding_count,
    )
