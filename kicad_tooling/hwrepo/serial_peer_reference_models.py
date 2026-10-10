"""Typed source-bound reports for serial peer-reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    Reference,
    RepositoryPath,
    StrictModel,
)


class SerialPeerReferenceLinkCoverageEntry(StrictModel):
    """Identity and disposition for one discovered native or label-based serial link."""

    discovery_basis: Literal["native_function", "channel_label"]
    first_reference: Identifier
    second_reference: Identifier
    signal_group: NonEmptyText
    signal_nets: Annotated[tuple[NetName, ...], Field(min_length=1)]
    signal_pins: Annotated[tuple[Reference, ...], Field(min_length=2)]
    disposition: Literal[
        "INCOMPLETE",
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]

    @model_validator(mode="after")
    def link_identity_is_consistent(self) -> SerialPeerReferenceLinkCoverageEntry:
        if self.first_reference.casefold() == self.second_reference.casefold():
            raise ValueError("Serial peer-reference links must join two different components")
        if self.discovery_basis == "native_function" and (
            len(self.signal_nets) != 1 or len(self.signal_pins) != 2
        ):
            raise ValueError("Native-function serial links need one net and two pins")
        if self.discovery_basis == "channel_label" and (
            len(self.signal_nets) != 2 or len(self.signal_pins) != 4
        ):
            raise ValueError("Channel-label serial links need two nets and four pins")
        return self


class SerialPeerReferenceCoverageReport(StrictModel):
    """Source-bound applicability counts for the direct UART reference heuristic."""

    rule_id: Literal["bus.serial_peer_reference_review"]
    status: Literal["NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    authored_map_state: Literal["not_configured", "pending", "not_applicable", "required"]
    authored_map_path: RepositoryPath | None = None
    authored_map_source_sha256: Digest | None = None
    authored_serial_peer_map_sha256: Digest | None = None
    # Optional for compatibility with earlier schema-version-2 reports.
    link_entries: tuple[SerialPeerReferenceLinkCoverageEntry, ...] | None = None
    native_peer_link_count: NonNegativeCount = 0
    label_peer_link_count: NonNegativeCount = 0
    supported_reference_link_count: NonNegativeCount = 0
    incomplete_reference_link_count: NonNegativeCount = 0
    common_reference_link_count: NonNegativeCount = 0
    separate_reference_link_count: NonNegativeCount = 0
    mapped_separate_reference_link_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0

    @model_validator(mode="after")
    def counts_match_scope(self) -> SerialPeerReferenceCoverageReport:
        if (self.authored_map_path is None) != (self.authored_map_source_sha256 is None):
            raise ValueError("Serial peer map path and source hash must be recorded together")
        if (self.authored_map_state == "required") != (
            self.authored_serial_peer_map_sha256 is not None
        ):
            raise ValueError("Serial peer map hash must match the authored map state")
        discovered = self.native_peer_link_count + self.label_peer_link_count
        if self.link_entries is not None:
            if len(self.link_entries) != discovered:
                raise ValueError("Serial link entries must account for every discovered peer link")
            entry_keys = {
                (
                    item.discovery_basis,
                    item.first_reference.casefold(),
                    item.second_reference.casefold(),
                    item.signal_group.casefold(),
                    item.signal_nets,
                    item.signal_pins,
                )
                for item in self.link_entries
            }
            if len(entry_keys) != len(self.link_entries):
                raise ValueError("Serial peer-reference link entries must be unique")
            if self.native_peer_link_count != sum(
                item.discovery_basis == "native_function" for item in self.link_entries
            ):
                raise ValueError("Native serial link count must match coverage entries")
            if self.label_peer_link_count != sum(
                item.discovery_basis == "channel_label" for item in self.link_entries
            ):
                raise ValueError("Serial label link count must match coverage entries")
            if self.incomplete_reference_link_count != sum(
                item.disposition == "INCOMPLETE" for item in self.link_entries
            ):
                raise ValueError("Incomplete serial link count must match coverage entries")
            if self.common_reference_link_count != sum(
                item.disposition == "COMMON_REFERENCE" for item in self.link_entries
            ):
                raise ValueError("Common-reference serial link count must match coverage entries")
            if self.separate_reference_link_count != sum(
                item.disposition in {"SEPARATE_REFERENCE_REVIEW", "MAP_COVERED_SEPARATE_REFERENCE"}
                for item in self.link_entries
            ):
                raise ValueError("Separate-reference serial link count must match coverage entries")
            if self.mapped_separate_reference_link_count != sum(
                item.disposition == "MAP_COVERED_SEPARATE_REFERENCE" for item in self.link_entries
            ):
                raise ValueError("Map-covered serial link count must match coverage entries")
            if self.candidate_group_count > sum(
                item.disposition == "SEPARATE_REFERENCE_REVIEW" for item in self.link_entries
            ):
                raise ValueError("Serial review groups need uncovered separate-reference links")
        if discovered != (
            self.supported_reference_link_count + self.incomplete_reference_link_count
        ):
            raise ValueError(
                "Serial reference evidence must account for every discovered peer link"
            )
        if self.supported_reference_link_count != (
            self.common_reference_link_count + self.separate_reference_link_count
        ):
            raise ValueError("Serial common and separate reference counts must balance")
        if self.mapped_separate_reference_link_count > self.separate_reference_link_count:
            raise ValueError("Map-covered serial links cannot exceed separate-reference links")
        if self.candidate_group_count > (
            self.separate_reference_link_count - self.mapped_separate_reference_link_count
        ):
            raise ValueError("Serial review groups need uncovered separate-reference links")
        expected_status = (
            "NO_DIRECT_PEERS"
            if discovered == 0
            else "INCOMPLETE"
            if self.incomplete_reference_link_count > 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Serial peer-reference coverage status does not match its counts")
        return self
