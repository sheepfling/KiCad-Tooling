"""Typed applicability coverage for shared-bus I2C reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NetName, NonNegativeCount, StrictModel


class I2cPeerReferenceBusCoverage(StrictModel):
    """Source-bound state for one shared I2C SDA/SCL net pair."""

    sda_net: NetName
    scl_net: NetName
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
    def disposition_matches_evidence(self) -> I2cPeerReferenceBusCoverage:
        if self.sda_net.casefold() == self.scl_net.casefold():
            raise ValueError("I2C peer-reference signal nets must be distinct")
        if len({item.casefold() for item in self.participants}) != len(self.participants):
            raise ValueError("I2C peer-reference bus participants must be unique")
        if len({item.casefold() for item in self.reference_nets}) != len(self.reference_nets):
            raise ValueError("I2C peer-reference nets must be unique")
        if len({item.casefold() for item in self.incomplete_references}) != len(
            self.incomplete_references
        ):
            raise ValueError("Incomplete I2C peer-reference identities must be unique")
        if not {item.casefold() for item in self.incomplete_references} <= {
            item.casefold() for item in self.participants
        }:
            raise ValueError("Incomplete I2C references must be bus participants")
        if self.disposition == "COMMON_REFERENCE" and (
            len(self.reference_nets) != 1 or self.incomplete_references
        ):
            raise ValueError("Common-reference I2C evidence must be complete and use one net")
        if self.disposition == "INCOMPLETE" and not self.incomplete_references:
            raise ValueError("Incomplete I2C reference evidence must name an endpoint")
        if self.disposition == "SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("I2C split-reference review needs two complete reference nets")
        if self.disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or not self.incomplete_references
        ):
            raise ValueError("Partial I2C split review needs split and incomplete evidence")
        if self.disposition == "COMPONENT_PEER_REVIEW_COVERS" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("Covered I2C split evidence needs complete distinct reference nets")
        return self


class I2cPeerReferenceCoverageReport(StrictModel):
    """Applicability counts for the source-bound I2C reference heuristic."""

    rule_id: Literal["bus.i2c_peer_reference_review"]
    status: Literal["NO_SHARED_BUS_PEERS", "INCOMPLETE", "EVALUATED"]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    recognized_endpoint_count: NonNegativeCount = 0
    shared_bus_count: NonNegativeCount = 0
    common_reference_bus_count: NonNegativeCount = 0
    incomplete_reference_bus_count: NonNegativeCount = 0
    split_reference_bus_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0
    component_peer_covered_bus_count: NonNegativeCount = 0
    entries: tuple[I2cPeerReferenceBusCoverage, ...] = ()

    @model_validator(mode="after")
    def counts_match_evidence(self) -> I2cPeerReferenceCoverageReport:
        if len(self.entries) != self.shared_bus_count:
            raise ValueError("I2C peer-reference entries must cover every shared bus")
        bus_keys = {(item.sda_net.casefold(), item.scl_net.casefold()) for item in self.entries}
        if len(bus_keys) != len(self.entries):
            raise ValueError("I2C peer-reference bus entries must be unique")
        expected_counts = (
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
        for actual, expected, label in expected_counts:
            if actual != expected:
                raise ValueError(f"I2C peer-reference {label} count does not match entries")
        if self.candidate_group_count + self.component_peer_covered_bus_count != (
            self.split_reference_bus_count
        ):
            raise ValueError("I2C split-reference candidates and covered groups must balance")
        if self.recognized_endpoint_count < sum(len(item.participants) for item in self.entries):
            raise ValueError("I2C peer-reference endpoint count cannot be below bus membership")
        expected_status = (
            "NO_SHARED_BUS_PEERS"
            if self.shared_bus_count == 0
            else "INCOMPLETE"
            if self.incomplete_reference_bus_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("I2C peer-reference status does not match its evidence counts")
        return self
