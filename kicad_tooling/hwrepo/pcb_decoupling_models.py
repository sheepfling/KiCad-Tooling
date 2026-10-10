"""Typed source-bound records for PCB decoupling coverage."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    Reference,
    RepositoryPath,
    StrictModel,
)


class PcbDecouplingCandidateObservation(StrictModel):
    """Observed exact capacitor identity, connectivity, and configured placement metrics."""

    reference: Identifier
    expected_footprint: NonEmptyText
    observed_footprint: NonEmptyText | None
    supply_pad: Reference
    return_pad: Reference
    observed_supply_net: NetName | None
    observed_return_net: NetName | None
    fitted: bool
    identity_matches: bool
    supply_connected: bool
    return_connected: bool
    distance_nm: NonNegativeCount | None
    distance_squared_nm2: NonNegativeCount | None
    connected_return_via_count: NonNegativeCount = 0
    nearest_return_via_id: Digest | None = None
    return_via_distance_nm: NonNegativeCount | None = None
    return_via_distance_squared_nm2: NonNegativeCount | None = None
    eligible: bool
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_distance(self) -> PcbDecouplingCandidateObservation:
        if (self.distance_nm is None) != (self.distance_squared_nm2 is None):
            raise ValueError("Decoupling candidate distance fields must be present together")
        if (self.return_via_distance_nm is None) != (self.return_via_distance_squared_nm2 is None):
            raise ValueError("Decoupling return-via distance fields must be present together")
        if (self.nearest_return_via_id is None) != (self.return_via_distance_nm is None):
            raise ValueError(
                "Decoupling return-via identity and measured distance must be present together"
            )
        if self.nearest_return_via_id is not None and self.connected_return_via_count == 0:
            raise ValueError("A nearest return via requires native-connected via evidence")
        if self.eligible and (
            not self.fitted
            or not self.identity_matches
            or not self.supply_connected
            or not self.return_connected
            or self.distance_nm is None
        ):
            raise ValueError("An eligible decoupling capacitor needs fitted connected geometry")
        return self


class PcbDecouplingCoverageEntry(StrictModel):
    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    ic_supply_pad: Reference
    ic_return_pad: Reference
    ic_supply_net: NetName
    ic_return_net: NetName
    max_distance_um: PositiveCount | None
    max_return_via_distance_um: PositiveCount | None = None
    selection: Literal["any", "all"]
    candidates: tuple[PcbDecouplingCandidateObservation, ...]
    selected_capacitors: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class PcbDecouplingCoverageReport(StrictModel):
    """Native PCB evidence for the explicitly mapped decoupling placement review."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[PcbDecouplingCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbDecouplingCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(
            item is None
            for item in (
                self.map_sha256,
                self.board_path,
                self.board_sha256,
                self.snapshot_path,
                self.snapshot_sha256,
                self.probe_sha256,
                self.kicad_version,
                self.image,
                self.netlist_sha256,
            )
        ):
            raise ValueError("Scanned PCB decoupling evidence must bind all source and tool inputs")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB decoupling coverage must explain the evidence gap")
        return self
