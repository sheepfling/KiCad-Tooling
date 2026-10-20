"""Typed coverage models for connector peer-pin review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    Reference,
    StrictModel,
)

ConnectorPinRole = Literal["signal", "return", "supply", "shield", "other"]


class SimilarConnectorPinGroup(StrictModel):
    """Unreviewed repeated connector pin functions with differing schematic nets."""

    symbol: NonEmptyText
    function: NonEmptyText
    pins: Mapping[Reference, tuple[NetName, ...]]
    reviewed_role: ConnectorPinRole | None = None
    reviewed_voltage_domain: NonEmptyText | None = None
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def mapped_supply_has_domain(self) -> SimilarConnectorPinGroup:
        if (self.reviewed_role == "supply") != (self.reviewed_voltage_domain is not None):
            raise ValueError("Mapped supply connector groups require an exact voltage domain")
        if self.reviewed_voltage_domain is not None and self.reviewed_role != "supply":
            raise ValueError("Only mapped supply connector groups carry a voltage domain")
        if (self.peer_assignment_group is None) != (not self.peer_assignment_basis):
            raise ValueError("Scoped connector comparisons need their reviewed group basis")
        return self


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


class ConnectorFootprintPeerPinCoverage(StrictModel):
    """Applicability evidence for cross-symbol connector footprint candidates."""

    status: Literal[
        "NO_CANDIDATES",
        "INCOMPLETE_EVIDENCE",
        "NO_PEER_SCOPES",
        "NO_COMPARABLE_ASSIGNMENTS",
        "NO_SHARED_ASSIGNMENT_ANCHOR",
        "NO_DIVERGENT_ASSIGNMENTS",
        "PARTIALLY_EVALUATED",
        "EVALUATED",
    ]
    netlist_sha256: Digest
    candidate_group_count: NonNegativeCount
    incomplete_pin_inventory_group_count: NonNegativeCount
    incomplete_pin_metadata_group_count: NonNegativeCount
    eligible_peer_group_count: NonNegativeCount
    peer_scope_group_count: NonNegativeCount
    evaluated_pin_group_count: NonNegativeCount
    compared_pin_group_count: NonNegativeCount
    common_assignment_pin_group_count: NonNegativeCount
    different_assignment_pin_group_count: NonNegativeCount
    unassigned_assignment_pin_group_count: NonNegativeCount
    ambiguous_assignment_pin_group_count: NonNegativeCount
    generic_different_assignment_pin_group_count: NonNegativeCount
    non_generic_different_assignment_pin_group_count: NonNegativeCount
    common_anchor_group_count: NonNegativeCount
    unanchored_different_assignment_pin_group_count: NonNegativeCount
    divergence_finding_count: NonNegativeCount
    open_peer_pin_group_count: NonNegativeCount
    unanchored_open_peer_pin_group_count: NonNegativeCount
    open_outlier_finding_count: NonNegativeCount
    all_open_peer_pin_group_count: NonNegativeCount = 0
    unanchored_all_open_peer_pin_group_count: NonNegativeCount = 0
    all_open_finding_count: NonNegativeCount = 0
    named_signal_different_assignment_pin_group_count: NonNegativeCount = 0
    unanchored_named_signal_divergence_pin_group_count: NonNegativeCount = 0
    named_signal_divergence_finding_count: NonNegativeCount = 0
    named_power_input_different_assignment_pin_group_count: NonNegativeCount = 0
    unanchored_named_power_input_divergence_pin_group_count: NonNegativeCount = 0
    named_power_input_divergence_finding_count: NonNegativeCount = 0
    named_power_output_different_assignment_pin_group_count: NonNegativeCount = 0
    unanchored_named_power_output_divergence_pin_group_count: NonNegativeCount = 0
    named_power_output_divergence_finding_count: NonNegativeCount = 0

    @model_validator(mode="after")
    def coverage_counts_match_scope(self) -> ConnectorFootprintPeerPinCoverage:
        if (
            self.incomplete_pin_inventory_group_count
            + self.incomplete_pin_metadata_group_count
            + self.eligible_peer_group_count
            != self.candidate_group_count
        ):
            raise ValueError("Footprint alias groups must have one evidence outcome")
        if self.compared_pin_group_count != (
            self.common_assignment_pin_group_count + self.different_assignment_pin_group_count
        ):
            raise ValueError("Compared footprint alias pin groups must have one assignment state")
        if self.evaluated_pin_group_count != (
            self.compared_pin_group_count
            + self.unassigned_assignment_pin_group_count
            + self.ambiguous_assignment_pin_group_count
        ):
            raise ValueError(
                "Evaluated footprint alias pin groups must have one assignment outcome"
            )
        if self.peer_scope_group_count < self.common_anchor_group_count:
            raise ValueError("Footprint alias anchor scopes cannot exceed peer scopes")
        if self.different_assignment_pin_group_count != (
            self.generic_different_assignment_pin_group_count
            + self.non_generic_different_assignment_pin_group_count
        ):
            raise ValueError("Footprint alias differences must separate generic and named pins")
        if self.unanchored_different_assignment_pin_group_count > (
            self.generic_different_assignment_pin_group_count
        ):
            raise ValueError("Unanchored differences must be generic differing pin groups")
        if self.divergence_finding_count + self.unanchored_different_assignment_pin_group_count != (
            self.generic_different_assignment_pin_group_count
        ):
            raise ValueError("Generic footprint alias differences must be anchored or unanchored")
        if self.unanchored_named_signal_divergence_pin_group_count > (
            self.named_signal_different_assignment_pin_group_count
        ):
            raise ValueError("Unanchored named signal divergences must be eligible differences")
        if (
            self.named_signal_divergence_finding_count
            + self.unanchored_named_signal_divergence_pin_group_count
            != self.named_signal_different_assignment_pin_group_count
        ):
            raise ValueError("Named signal differences must be anchored findings or unanchored")
        if self.unanchored_named_power_input_divergence_pin_group_count > (
            self.named_power_input_different_assignment_pin_group_count
        ):
            raise ValueError("Unanchored named power-input differences must be eligible")
        if (
            self.named_power_input_divergence_finding_count
            + self.unanchored_named_power_input_divergence_pin_group_count
            != self.named_power_input_different_assignment_pin_group_count
        ):
            raise ValueError(
                "Named power-input differences must be anchored findings or unanchored"
            )
        if self.unanchored_named_power_output_divergence_pin_group_count > (
            self.named_power_output_different_assignment_pin_group_count
        ):
            raise ValueError("Unanchored named power-output differences must be eligible")
        if (
            self.named_power_output_divergence_finding_count
            + self.unanchored_named_power_output_divergence_pin_group_count
            != self.named_power_output_different_assignment_pin_group_count
        ):
            raise ValueError(
                "Named power-output differences must be anchored findings or unanchored"
            )
        if self.open_peer_pin_group_count > self.unassigned_assignment_pin_group_count:
            raise ValueError("Footprint alias open peers must have an unassigned peer contact")
        if self.unanchored_open_peer_pin_group_count > self.open_peer_pin_group_count:
            raise ValueError("Unanchored open peers cannot exceed open peer pin groups")
        if (
            self.open_outlier_finding_count + self.unanchored_open_peer_pin_group_count
            != self.open_peer_pin_group_count
        ):
            raise ValueError("Footprint alias open peers must be anchored or unanchored")
        if self.all_open_peer_pin_group_count > self.unassigned_assignment_pin_group_count:
            raise ValueError("All-open footprint alias peers must be unassigned pin groups")
        if self.unanchored_all_open_peer_pin_group_count > self.all_open_peer_pin_group_count:
            raise ValueError("Unanchored all-open peers cannot exceed all-open peer pin groups")
        if (
            self.all_open_finding_count + self.unanchored_all_open_peer_pin_group_count
            != self.all_open_peer_pin_group_count
        ):
            raise ValueError("All-open footprint aliases must be anchored or unanchored")

        incomplete_count = (
            self.incomplete_pin_inventory_group_count
            + self.incomplete_pin_metadata_group_count
            + self.unassigned_assignment_pin_group_count
            + self.ambiguous_assignment_pin_group_count
        )
        expected_status = (
            "NO_CANDIDATES"
            if self.candidate_group_count == 0
            else "INCOMPLETE_EVIDENCE"
            if self.eligible_peer_group_count == 0
            else "NO_PEER_SCOPES"
            if self.peer_scope_group_count == 0
            else "NO_COMPARABLE_ASSIGNMENTS"
            if self.evaluated_pin_group_count == 0
            else "NO_SHARED_ASSIGNMENT_ANCHOR"
            if self.common_anchor_group_count == 0
            else "PARTIALLY_EVALUATED"
            if incomplete_count > 0
            else "NO_DIVERGENT_ASSIGNMENTS"
            if (
                self.generic_different_assignment_pin_group_count
                + self.named_signal_different_assignment_pin_group_count
                + self.named_power_input_different_assignment_pin_group_count
                + self.named_power_output_different_assignment_pin_group_count
                == 0
            )
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Footprint alias peer status does not match its counts")
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
    footprint_alias_coverage: ConnectorFootprintPeerPinCoverage
    incomplete_pin_inventory_references: tuple[Reference, ...] = ()
    repeated_function_group_count: NonNegativeCount
    repeated_function_groups_with_common_assignment_count: NonNegativeCount
    repeated_function_groups_with_different_assignments_count: NonNegativeCount
    repeated_function_groups_all_unassigned_count: NonNegativeCount
    repeated_function_groups_with_open_assignment_count: NonNegativeCount
    repeated_function_finding_count: NonNegativeCount
    peer_pin_outlier_finding_count: NonNegativeCount
    peer_pin_divergence_finding_count: NonNegativeCount
    generic_peer_pin_all_open_finding_count: NonNegativeCount = 0

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
        if self.footprint_alias_coverage.netlist_sha256 != self.netlist_sha256:
            raise ValueError(
                "Connector footprint alias coverage must use this report's native netlist"
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
            self.peer_pin_outlier_finding_count
            + self.peer_pin_divergence_finding_count
            + self.footprint_alias_coverage.open_outlier_finding_count
            + self.footprint_alias_coverage.named_signal_divergence_finding_count
            + self.footprint_alias_coverage.named_power_input_divergence_finding_count
            + self.footprint_alias_coverage.named_power_output_divergence_finding_count
            + self.footprint_alias_coverage.all_open_finding_count
            > self.exact_symbol_pin_group_count
            + self.part_id_alias_coverage.compared_pin_group_count
            + self.footprint_alias_coverage.compared_pin_group_count
            + self.footprint_alias_coverage.all_open_peer_pin_group_count
        ):
            raise ValueError("Peer-pin findings cannot exceed compared connector pin groups")
        if self.generic_peer_pin_all_open_finding_count > (
            self.exact_symbol_pin_groups_all_unassigned_count
            + self.part_id_alias_coverage.all_unassigned_pin_group_count
        ):
            raise ValueError(
                "All-open generic findings cannot exceed all-unassigned exact-symbol and PART_ID groups"
            )
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
