"""Typed coverage model for component peer-pin review."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonNegativeCount, Reference, StrictModel


class ComponentPeerPinRuleCoverage(StrictModel):
    """Source-bound applicability counts for one typed component-peer pin rule."""

    rule_id: Literal[
        "component.peer_power_output_unconnected",
        "component.peer_signal_output_unconnected",
        "component.peer_signal_input_unconnected",
        "component.peer_bidirectional_pin_unconnected",
    ]
    status: Literal[
        "NO_COMPARABLE_PEERS",
        "INCOMPLETE_COMPONENT_IDENTITY",
        "INCOMPLETE_PIN_INVENTORY",
        "NO_MATCHING_PIN_TYPES",
        "NO_COMPATIBLE_PIN_FUNCTIONS",
        "NO_UNAMBIGUOUS_ASSIGNMENTS",
        "PARTIALLY_EVALUATED",
        "EVALUATED",
    ]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    exact_symbol_peer_group_count: NonNegativeCount
    part_id_peer_group_count: NonNegativeCount
    part_id_candidate_group_count: NonNegativeCount = 0
    part_id_incomplete_component_identity_group_count: NonNegativeCount = 0
    part_id_incomplete_component_identity_references: tuple[Reference, ...] = ()
    incomplete_pin_inventory_group_count: NonNegativeCount
    incomplete_pin_inventory_references: tuple[Reference, ...] = ()
    complete_pin_inventory_group_count: NonNegativeCount
    comparable_pin_group_count: NonNegativeCount
    matching_electrical_type_pin_group_count: NonNegativeCount
    compatible_function_pin_group_count: NonNegativeCount
    ambiguous_assignment_pin_group_count: NonNegativeCount
    unambiguous_assignment_pin_group_count: NonNegativeCount
    candidate_group_count: NonNegativeCount
    deduplicated_candidate_group_count: NonNegativeCount
    finding_count: NonNegativeCount
    suppressed_candidate_count: NonNegativeCount

    @model_validator(mode="after")
    def coverage_counts_match_scope(self) -> ComponentPeerPinRuleCoverage:
        if len(set(self.part_id_incomplete_component_identity_references)) != len(
            self.part_id_incomplete_component_identity_references
        ):
            raise ValueError("Incomplete component identity references must be unique")
        if (
            any(
                (
                    self.part_id_candidate_group_count,
                    self.part_id_incomplete_component_identity_group_count,
                    self.part_id_incomplete_component_identity_references,
                )
            )
            and self.part_id_peer_group_count
            + (self.part_id_incomplete_component_identity_group_count)
            != self.part_id_candidate_group_count
        ):
            raise ValueError("Component PART_ID candidates must have one identity outcome")
        if self.part_id_incomplete_component_identity_group_count > (
            self.part_id_candidate_group_count
        ):
            raise ValueError("Incomplete component identities cannot exceed PART_ID candidates")
        if (self.part_id_incomplete_component_identity_group_count == 0) != (
            len(self.part_id_incomplete_component_identity_references) == 0
        ):
            raise ValueError("Incomplete component identity counts must match their references")
        if len(set(self.incomplete_pin_inventory_references)) != len(
            self.incomplete_pin_inventory_references
        ):
            raise ValueError("Incomplete component peer inventory references must be unique")
        peer_group_count = self.exact_symbol_peer_group_count + self.part_id_peer_group_count
        if self.incomplete_pin_inventory_group_count > peer_group_count:
            raise ValueError("Incomplete peer inventories cannot exceed comparable peer groups")
        if self.complete_pin_inventory_group_count > peer_group_count:
            raise ValueError("Complete peer inventories cannot exceed comparable peer groups")
        if self.incomplete_pin_inventory_group_count + self.complete_pin_inventory_group_count != (
            peer_group_count
        ):
            raise ValueError("Peer component groups must have complete or incomplete inventories")
        if (self.incomplete_pin_inventory_group_count == 0) != (
            len(self.incomplete_pin_inventory_references) == 0
        ):
            raise ValueError("Incomplete peer inventory counts must match their references")
        if self.matching_electrical_type_pin_group_count > self.comparable_pin_group_count:
            raise ValueError("Matching peer pin types cannot exceed comparable pin groups")
        if self.compatible_function_pin_group_count > (
            self.matching_electrical_type_pin_group_count
        ):
            raise ValueError("Compatible peer pin functions require matching native pin types")
        if (
            self.ambiguous_assignment_pin_group_count
            + (self.unambiguous_assignment_pin_group_count)
            != self.compatible_function_pin_group_count
        ):
            raise ValueError("Compatible peer pin groups must have unambiguous or ambiguous nets")
        if self.candidate_group_count > self.unambiguous_assignment_pin_group_count:
            raise ValueError("Peer-pin candidates require unambiguous assignments")
        if self.deduplicated_candidate_group_count > self.unambiguous_assignment_pin_group_count:
            raise ValueError("Deduplicated peer-pin candidates require unambiguous assignments")
        if self.finding_count + self.suppressed_candidate_count != self.candidate_group_count:
            raise ValueError("Peer-pin findings and suppressed candidates must balance")

        expected_status = (
            "INCOMPLETE_COMPONENT_IDENTITY"
            if peer_group_count == 0 and self.part_id_candidate_group_count > 0
            else "NO_COMPARABLE_PEERS"
            if peer_group_count == 0
            else "INCOMPLETE_PIN_INVENTORY"
            if self.complete_pin_inventory_group_count == 0
            else "NO_MATCHING_PIN_TYPES"
            if self.matching_electrical_type_pin_group_count == 0
            else "NO_COMPATIBLE_PIN_FUNCTIONS"
            if self.compatible_function_pin_group_count == 0
            else "NO_UNAMBIGUOUS_ASSIGNMENTS"
            if self.unambiguous_assignment_pin_group_count == 0
            else "PARTIALLY_EVALUATED"
            if (
                self.incomplete_pin_inventory_group_count > 0
                or self.part_id_incomplete_component_identity_group_count > 0
            )
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Component peer-pin coverage status does not match its counts")
        return self
