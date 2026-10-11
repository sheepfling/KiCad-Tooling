"""Typed source-bound coverage for mapped RS-485 peer reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonNegativeCount,
    RepositoryPath,
    StrictModel,
)


class Rs485PeerReferencePairCoverage(StrictModel):
    """Applicability and reference disposition for one exact authored line pair."""

    bus_id: Identifier
    pair_id: Identifier
    line_1_net: NetName
    line_2_net: NetName
    participants: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    reference_nets: tuple[NetName, ...] = ()
    incomplete_references: tuple[Identifier, ...] = ()
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
    ]

    @model_validator(mode="after")
    def disposition_matches_evidence(self) -> Rs485PeerReferencePairCoverage:
        if self.line_1_net.casefold() == self.line_2_net.casefold():
            raise ValueError("RS-485 peer-reference line nets must be distinct")
        for values, label in (
            (self.participants, "participants"),
            (self.reference_nets, "reference nets"),
            (self.incomplete_references, "incomplete references"),
        ):
            if len({item.casefold() for item in values}) != len(values):
                raise ValueError(f"RS-485 peer-reference {label} must be unique")
        if not {item.casefold() for item in self.incomplete_references} <= {
            item.casefold() for item in self.participants
        }:
            raise ValueError("Incomplete RS-485 references must be pair participants")
        if self.disposition == "COMMON_REFERENCE" and (
            len(self.reference_nets) != 1 or self.incomplete_references
        ):
            raise ValueError("Common-reference RS-485 evidence needs one complete reference net")
        if self.disposition == "INCOMPLETE" and (
            not self.incomplete_references or len(self.reference_nets) > 1
        ):
            raise ValueError("Incomplete RS-485 evidence cannot already establish a split")
        if self.disposition == "SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("RS-485 split review needs two complete reference nets")
        if self.disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or not self.incomplete_references
        ):
            raise ValueError("Partial RS-485 split review needs split and incomplete evidence")
        return self


class Rs485PeerReferenceCoverageReport(StrictModel):
    """Source hashes, applicability, and finding counts for the RS-485 heuristic."""

    rule_id: Literal["bus.rs485_peer_reference_review"] = "bus.rs485_peer_reference_review"
    status: Literal[
        "NOT_CONFIGURED",
        "PENDING",
        "NOT_APPLICABLE",
        "NO_SHARED_ENDPOINTS",
        "INCOMPLETE",
        "EVALUATED",
    ]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    authored_map_state: Literal["not_configured", "pending", "not_applicable", "required"]
    authored_map_path: RepositoryPath | None = None
    authored_map_source_sha256: Digest | None = None
    authored_rs485_map_sha256: Digest | None = None
    recognized_endpoint_count: NonNegativeCount = 0
    shared_pair_count: NonNegativeCount = 0
    common_reference_pair_count: NonNegativeCount = 0
    incomplete_reference_pair_count: NonNegativeCount = 0
    split_reference_pair_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0
    entries: tuple[Rs485PeerReferencePairCoverage, ...] = ()

    @model_validator(mode="after")
    def source_and_counts_match(self) -> Rs485PeerReferenceCoverageReport:
        if (self.authored_map_path is None) != (self.authored_map_source_sha256 is None):
            raise ValueError("RS-485 map path and source hash must be recorded together")
        if (self.authored_map_state == "required") != (self.authored_rs485_map_sha256 is not None):
            raise ValueError("RS-485 map digest must match the authored map state")
        if len(self.entries) != self.shared_pair_count:
            raise ValueError("RS-485 peer-reference entries must cover every shared pair")
        keys = {(item.bus_id.casefold(), item.pair_id.casefold()) for item in self.entries}
        if len(keys) != len(self.entries):
            raise ValueError("RS-485 peer-reference pair entries must be unique")
        expected_counts = (
            (
                self.common_reference_pair_count,
                sum(item.disposition == "COMMON_REFERENCE" for item in self.entries),
                "common-reference",
            ),
            (
                self.incomplete_reference_pair_count,
                sum(
                    item.disposition in {"INCOMPLETE", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
                    for item in self.entries
                ),
                "incomplete-reference",
            ),
            (
                self.split_reference_pair_count,
                sum(
                    item.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
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
        )
        for actual, expected, label in expected_counts:
            if actual != expected:
                raise ValueError(f"RS-485 peer-reference {label} count does not match entries")
        if self.recognized_endpoint_count < len(
            {reference.casefold() for item in self.entries for reference in item.participants}
        ):
            raise ValueError("RS-485 recognized endpoint count cannot be below pair membership")
        expected_status = {
            "not_configured": "NOT_CONFIGURED",
            "pending": "PENDING",
            "not_applicable": "NOT_APPLICABLE",
        }.get(self.authored_map_state)
        if expected_status is None:
            expected_status = (
                "NO_SHARED_ENDPOINTS"
                if self.shared_pair_count == 0
                else "INCOMPLETE"
                if self.incomplete_reference_pair_count
                else "EVALUATED"
            )
        if self.status != expected_status:
            raise ValueError("RS-485 peer-reference status does not match its scope and evidence")
        return self
