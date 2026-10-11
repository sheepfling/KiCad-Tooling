"""Typed applicability coverage for CAN peer-reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NetName, NonNegativeCount, StrictModel


class CanPeerReferenceBusCoverage(StrictModel):
    """Source-bound state for one shared native CANH/CANL pair."""

    canh_net: NetName
    canl_net: NetName
    participants: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    reference_nets: tuple[NetName, ...] = ()
    incomplete_references: tuple[Identifier, ...] = ()
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
        "COMPONENT_PEER_REVIEW_COVERS",
    ]

    @model_validator(mode="after")
    def disposition_matches_evidence(self) -> CanPeerReferenceBusCoverage:
        if self.canh_net.casefold() == self.canl_net.casefold():
            raise ValueError("CAN peer-reference signal nets must be distinct")
        for values, label in (
            (self.participants, "participants"),
            (self.reference_nets, "reference nets"),
            (self.incomplete_references, "incomplete references"),
        ):
            if len({item.casefold() for item in values}) != len(values):
                raise ValueError(f"CAN peer-reference {label} must be unique")
        if not {item.casefold() for item in self.incomplete_references} <= {
            item.casefold() for item in self.participants
        }:
            raise ValueError("Incomplete CAN references must be bus participants")
        if self.disposition == "COMMON_REFERENCE" and (
            len(self.reference_nets) != 1 or self.incomplete_references
        ):
            raise ValueError("Common-reference CAN evidence must be complete and use one net")
        if self.disposition == "INCOMPLETE" and (
            not self.incomplete_references or len(self.reference_nets) > 1
        ):
            raise ValueError("Incomplete CAN evidence must name an endpoint without a known split")
        if self.disposition == "SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("CAN split-reference review needs two complete reference nets")
        if self.disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or not self.incomplete_references
        ):
            raise ValueError("Partial CAN split review needs split and incomplete evidence")
        if self.disposition == "COMPONENT_PEER_REVIEW_COVERS" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("Covered CAN split evidence needs complete distinct reference nets")
        return self


class CanPeerReferenceCoverageReport(StrictModel):
    """Applicability counts for the source-bound CAN reference heuristic."""

    rule_id: Literal["bus.can_peer_reference_review"]
    status: Literal["NO_SHARED_CAN_BUSES", "INCOMPLETE", "EVALUATED"]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    recognized_endpoint_count: NonNegativeCount = 0
    shared_can_bus_count: NonNegativeCount = 0
    common_reference_bus_count: NonNegativeCount = 0
    incomplete_reference_bus_count: NonNegativeCount = 0
    split_reference_bus_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0
    component_peer_covered_bus_count: NonNegativeCount = 0
    entries: tuple[CanPeerReferenceBusCoverage, ...] = ()

    @model_validator(mode="after")
    def counts_match_evidence(self) -> CanPeerReferenceCoverageReport:
        if len(self.entries) != self.shared_can_bus_count:
            raise ValueError("CAN peer-reference entries must cover every shared line pair")
        bus_keys = {(item.canh_net.casefold(), item.canl_net.casefold()) for item in self.entries}
        if len(bus_keys) != len(self.entries):
            raise ValueError("CAN peer-reference bus entries must be unique")
        checks = (
            (
                self.common_reference_bus_count,
                sum(item.disposition == "COMMON_REFERENCE" for item in self.entries),
                "common-reference",
            ),
            (
                self.incomplete_reference_bus_count,
                sum(
                    item.disposition in {"INCOMPLETE", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
                    for item in self.entries
                ),
                "incomplete-reference",
            ),
            (
                self.split_reference_bus_count,
                sum(
                    item.disposition
                    in {
                        "SPLIT_REFERENCE_REVIEW",
                        "PARTIAL_SPLIT_REFERENCE_REVIEW",
                        "COMPONENT_PEER_REVIEW_COVERS",
                    }
                    for item in self.entries
                ),
                "split-reference",
            ),
            (
                self.candidate_group_count,
                sum(
                    item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
                    for item in self.entries
                ),
                "candidate",
            ),
            (
                self.component_peer_covered_bus_count,
                sum(item.disposition == "COMPONENT_PEER_REVIEW_COVERS" for item in self.entries),
                "component-peer-covered",
            ),
        )
        for actual, expected, label in checks:
            if actual != expected:
                raise ValueError(f"CAN peer-reference {label} count does not match entries")
        if self.candidate_group_count + self.component_peer_covered_bus_count != (
            self.split_reference_bus_count
        ):
            raise ValueError("CAN split-reference candidates and covered groups must balance")
        if self.recognized_endpoint_count < sum(len(item.participants) for item in self.entries):
            raise ValueError("CAN peer-reference endpoint count cannot be below bus membership")
        expected_status = (
            "NO_SHARED_CAN_BUSES"
            if self.shared_can_bus_count == 0
            else "INCOMPLETE"
            if self.incomplete_reference_bus_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("CAN peer-reference status does not match its evidence counts")
        return self
