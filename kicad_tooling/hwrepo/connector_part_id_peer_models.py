"""Typed coverage model for cross-symbol connector PART_ID comparisons."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonNegativeCount, Reference, StrictModel


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
    differing_pin_metadata_group_count: NonNegativeCount = 0
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
        if (
            self.incomplete_component_identity_group_count
            + self.incomplete_pin_inventory_group_count
            + self.incomplete_pin_metadata_group_count
            + self.differing_pin_metadata_group_count
            + self.eligible_peer_group_count
            != self.candidate_group_count
        ):
            raise ValueError("Connector PART_ID peer groups must have one evidence outcome")
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
            if self.eligible_peer_group_count == 0 and self.differing_pin_metadata_group_count == 0
            else "PARTIALLY_EVALUATED"
            if self.differing_pin_metadata_group_count > 0
            else "NO_COMPARABLE_PIN_GROUPS"
            if self.compared_pin_group_count == 0
            else "PARTIALLY_EVALUATED"
            if incomplete_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Connector PART_ID peer status does not match its counts")
        return self
