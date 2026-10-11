"""Typed applicability coverage for direct SPI clock reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NetName, NonNegativeCount, StrictModel


class SpiClockPeerCoverage(StrictModel):
    """Source-bound state for fitted ICs sharing one native SCK/SCLK net."""

    clock_net: NetName
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
    def disposition_matches_evidence(self) -> SpiClockPeerCoverage:
        if len({item.casefold() for item in self.participants}) != len(self.participants):
            raise ValueError("SPI peer-reference participants must be unique")
        if len({item.casefold() for item in self.reference_nets}) != len(self.reference_nets):
            raise ValueError("SPI peer-reference nets must be unique")
        if len({item.casefold() for item in self.incomplete_references}) != len(
            self.incomplete_references
        ):
            raise ValueError("Incomplete SPI peer-reference identities must be unique")
        if not {item.casefold() for item in self.incomplete_references} <= {
            item.casefold() for item in self.participants
        }:
            raise ValueError("Incomplete SPI references must be clock participants")
        if self.disposition == "COMMON_REFERENCE" and (
            len(self.reference_nets) != 1 or self.incomplete_references
        ):
            raise ValueError("Common-reference SPI evidence must be complete and use one net")
        if self.disposition == "INCOMPLETE" and (
            not self.incomplete_references or len(self.reference_nets) > 1
        ):
            raise ValueError("Incomplete SPI evidence must name an endpoint without a known split")
        if self.disposition == "SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("SPI split-reference review needs two complete reference nets")
        if self.disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW" and (
            len(self.reference_nets) < 2 or not self.incomplete_references
        ):
            raise ValueError("Partial SPI split review needs split and incomplete evidence")
        if self.disposition == "COMPONENT_PEER_REVIEW_COVERS" and (
            len(self.reference_nets) < 2 or self.incomplete_references
        ):
            raise ValueError("Covered SPI split evidence needs complete distinct reference nets")
        return self


class SpiPeerReferenceCoverageReport(StrictModel):
    """Applicability counts for the source-bound SPI reference heuristic."""

    rule_id: Literal["bus.spi_peer_reference_review"]
    status: Literal["NO_SHARED_CLOCK_PEERS", "INCOMPLETE", "EVALUATED"]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    recognized_endpoint_count: NonNegativeCount = 0
    shared_clock_bus_count: NonNegativeCount = 0
    common_reference_bus_count: NonNegativeCount = 0
    incomplete_reference_bus_count: NonNegativeCount = 0
    split_reference_bus_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0
    component_peer_covered_bus_count: NonNegativeCount = 0
    entries: tuple[SpiClockPeerCoverage, ...] = ()

    @model_validator(mode="after")
    def counts_match_evidence(self) -> SpiPeerReferenceCoverageReport:
        if len(self.entries) != self.shared_clock_bus_count:
            raise ValueError("SPI peer-reference entries must cover every shared clock net")
        clock_nets = {item.clock_net.casefold() for item in self.entries}
        if len(clock_nets) != len(self.entries):
            raise ValueError("SPI peer-reference clock entries must be unique")
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
                raise ValueError(f"SPI peer-reference {label} count does not match entries")
        if self.candidate_group_count + self.component_peer_covered_bus_count != (
            self.split_reference_bus_count
        ):
            raise ValueError("SPI split-reference candidates and covered groups must balance")
        if self.recognized_endpoint_count < sum(len(item.participants) for item in self.entries):
            raise ValueError("SPI peer-reference endpoint count cannot be below bus membership")
        expected_status = (
            "NO_SHARED_CLOCK_PEERS"
            if self.shared_clock_bus_count == 0
            else "INCOMPLETE"
            if self.incomplete_reference_bus_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("SPI peer-reference status does not match evidence counts")
        return self
