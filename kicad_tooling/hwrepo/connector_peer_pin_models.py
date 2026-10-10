"""Typed coverage models for connector peer-pin review."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonEmptyText, NonNegativeCount, Reference, StrictModel


class ConnectorPartIdPeerPinCoverage(StrictModel):
    """Applicability evidence for cross-symbol connector PART_ID comparisons."""

    status: Literal[
        "NO_CANDIDATES",
        "INCOMPLETE_EVIDENCE",
        "NO_COMPARABLE_PIN_GROUPS",
        "PARTIALLY_EVALUATED",
        "EVALUATED",
    ]
    netlist_sha256: Digest
    candidate_group_count: NonNegativeCount
    incomplete_component_identity_group_count: NonNegativeCount
    incomplete_pin_inventory_group_count: NonNegativeCount
    incomplete_pin_metadata_group_count: NonNegativeCount
    eligible_peer_group_count: NonNegativeCount
    incomplete_pin_inventory_references: tuple[Reference, ...] = ()
    compared_pin_group_count: NonNegativeCount
    unknown_function_pin_group_count: NonNegativeCount
    meaningful_function_pin_group_count: NonNegativeCount
    ambiguous_assignment_pin_group_count: NonNegativeCount
    common_assignment_pin_group_count: NonNegativeCount
    different_assignment_pin_group_count: NonNegativeCount
    all_unassigned_pin_group_count: NonNegativeCount
    open_assignment_pin_group_count: NonNegativeCount
    outlier_finding_count: NonNegativeCount
    divergence_finding_count: NonNegativeCount

    @model_validator(mode="after")
    def coverage_counts_match_scope(self) -> ConnectorPartIdPeerPinCoverage:
        if self.incomplete_component_identity_group_count + (
            self.incomplete_pin_inventory_group_count
        ) + self.incomplete_pin_metadata_group_count + self.eligible_peer_group_count != (
            self.candidate_group_count
        ):
            raise ValueError("Connector PART_ID peer groups must have one identity outcome")
        if self.compared_pin_group_count != (
            self.ambiguous_assignment_pin_group_count
            + self.common_assignment_pin_group_count
            + self.different_assignment_pin_group_count
            + self.all_unassigned_pin_group_count
        ):
            raise ValueError("Connector PART_ID pin states must account for every compared group")
        if self.compared_pin_group_count != (
            self.unknown_function_pin_group_count + self.meaningful_function_pin_group_count
        ):
            raise ValueError("Connector PART_ID function states must account for every pin group")
        if self.open_assignment_pin_group_count > (
            self.different_assignment_pin_group_count + self.all_unassigned_pin_group_count
        ):
            raise ValueError("Open connector PART_ID assignments must be classified as different")
        if self.outlier_finding_count + self.divergence_finding_count > (
            self.compared_pin_group_count
        ):
            raise ValueError("Connector PART_ID findings cannot exceed compared pin groups")
        if len(set(self.incomplete_pin_inventory_references)) != len(
            self.incomplete_pin_inventory_references
        ):
            raise ValueError("Incomplete PART_ID peer inventory references must be unique")
        if (self.incomplete_pin_inventory_group_count == 0) != (
            len(self.incomplete_pin_inventory_references) == 0
        ):
            raise ValueError("Incomplete PART_ID inventory counts must match their references")

        incomplete_count = (
            self.incomplete_component_identity_group_count
            + self.incomplete_pin_inventory_group_count
            + self.incomplete_pin_metadata_group_count
        )
        expected_status = (
            "NO_CANDIDATES"
            if self.candidate_group_count == 0
            else "INCOMPLETE_EVIDENCE"
            if self.eligible_peer_group_count == 0
            else "NO_COMPARABLE_PIN_GROUPS"
            if self.compared_pin_group_count == 0
            else "PARTIALLY_EVALUATED"
            if incomplete_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Connector PART_ID peer status does not match its counts")
        return self


class ConnectorPeerPinHeuristicCoverage(StrictModel):
    """Source-bound applicability counts for connector pin peer heuristics."""

    status: Literal[
        "NO_CONNECTOR_CANDIDATES",
        "NO_FITTED_CONNECTORS",
        "NO_EXACT_SYMBOL_PEERS",
        "NO_COMPARABLE_PIN_GROUPS",
        "INCOMPLETE_PIN_INVENTORY",
        "EVALUATED",
    ]
    netlist_sha256: Digest
    scope: NonEmptyText
    connector_candidate_count: NonNegativeCount
    fitted_connector_count: NonNegativeCount
    exact_symbol_peer_group_count: NonNegativeCount
    exact_symbol_pin_group_count: NonNegativeCount
    exact_symbol_pin_groups_with_unknown_function_count: NonNegativeCount
    exact_symbol_pin_groups_with_meaningful_functions_count: NonNegativeCount
    exact_symbol_pin_groups_with_common_assignment_count: NonNegativeCount
    exact_symbol_pin_groups_with_different_assignments_count: NonNegativeCount
    exact_symbol_pin_groups_all_unassigned_count: NonNegativeCount
    exact_symbol_pin_groups_with_open_assignment_count: NonNegativeCount
    part_id_alias_coverage: ConnectorPartIdPeerPinCoverage
    incomplete_pin_inventory_references: tuple[Reference, ...] = ()
    repeated_function_group_count: NonNegativeCount
    repeated_function_groups_with_common_assignment_count: NonNegativeCount
    repeated_function_groups_with_different_assignments_count: NonNegativeCount
    repeated_function_groups_all_unassigned_count: NonNegativeCount
    repeated_function_groups_with_open_assignment_count: NonNegativeCount
    repeated_function_finding_count: NonNegativeCount
    peer_pin_outlier_finding_count: NonNegativeCount
    peer_pin_divergence_finding_count: NonNegativeCount

    @model_validator(mode="after")
    def consistent_connector_peer_coverage(self) -> ConnectorPeerPinHeuristicCoverage:
        if self.fitted_connector_count > self.connector_candidate_count:
            raise ValueError("Fitted connector count cannot exceed candidate connector count")
        if self.exact_symbol_peer_group_count > self.fitted_connector_count:
            raise ValueError("Exact-symbol peer groups cannot exceed fitted connector count")
        if self.exact_symbol_peer_group_count > self.fitted_connector_count // 2:
            raise ValueError("Each exact-symbol peer group requires at least two fitted connectors")
        if self.part_id_alias_coverage.netlist_sha256 != self.netlist_sha256:
            raise ValueError(
                "Connector PART_ID alias coverage must use this report's native netlist"
            )
        if self.exact_symbol_pin_group_count != (
            self.exact_symbol_pin_groups_with_common_assignment_count
            + self.exact_symbol_pin_groups_with_different_assignments_count
            + self.exact_symbol_pin_groups_all_unassigned_count
        ):
            raise ValueError("Exact-symbol pin assignment states must account for every peer group")
        if self.exact_symbol_pin_groups_with_open_assignment_count > (
            self.exact_symbol_pin_groups_with_different_assignments_count
            + self.exact_symbol_pin_groups_all_unassigned_count
        ):
            raise ValueError(
                "Open exact-symbol assignments must be classified as different or empty"
            )
        if self.exact_symbol_pin_group_count != (
            self.exact_symbol_pin_groups_with_unknown_function_count
            + self.exact_symbol_pin_groups_with_meaningful_functions_count
        ):
            raise ValueError("Exact-symbol function states must account for every peer group")
        if self.repeated_function_group_count != (
            self.repeated_function_groups_with_common_assignment_count
            + self.repeated_function_groups_with_different_assignments_count
            + self.repeated_function_groups_all_unassigned_count
        ):
            raise ValueError("Repeated-function assignment states must account for every group")
        if self.repeated_function_groups_with_open_assignment_count > (
            self.repeated_function_groups_with_different_assignments_count
            + self.repeated_function_groups_all_unassigned_count
        ):
            raise ValueError(
                "Open repeated-function assignments must be classified as different or empty"
            )
        if self.repeated_function_finding_count > self.repeated_function_group_count:
            raise ValueError("Repeated-function findings cannot exceed compared groups")
        if (
            self.peer_pin_outlier_finding_count + self.peer_pin_divergence_finding_count
            > self.exact_symbol_pin_group_count
            + self.part_id_alias_coverage.compared_pin_group_count
        ):
            raise ValueError("Peer-pin findings cannot exceed compared connector pin groups")
        if self.status == "NO_CONNECTOR_CANDIDATES" and self.connector_candidate_count:
            raise ValueError("No-connector coverage cannot contain connector candidates")
        if self.status == "NO_FITTED_CONNECTORS" and (
            not self.connector_candidate_count or self.fitted_connector_count
        ):
            raise ValueError("No-fitted coverage requires candidates that are all unpopulated")
        if self.status == "NO_EXACT_SYMBOL_PEERS" and self.exact_symbol_peer_group_count:
            raise ValueError("No-peer coverage cannot contain exact-symbol peer groups")
        if self.status == "NO_EXACT_SYMBOL_PEERS" and (
            not self.connector_candidate_count or not self.fitted_connector_count
        ):
            raise ValueError("No-peer coverage requires at least one fitted connector candidate")
        if self.status == "NO_COMPARABLE_PIN_GROUPS" and (
            not self.exact_symbol_peer_group_count
            or self.exact_symbol_pin_group_count
            or self.incomplete_pin_inventory_references
        ):
            raise ValueError(
                "No-comparable-pin coverage requires complete but empty peer inventories"
            )
        if self.status == "INCOMPLETE_PIN_INVENTORY" and not (
            self.incomplete_pin_inventory_references
        ):
            raise ValueError("Incomplete connector peer coverage requires missing pin inventories")
        if self.status == "EVALUATED" and not self.exact_symbol_pin_group_count:
            raise ValueError("Evaluated connector peer coverage requires comparable pin groups")
        return self
