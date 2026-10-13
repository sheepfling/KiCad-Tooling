"""Typed source-bound records for PCB decoupling coverage."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

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


class PcbDecouplingCapacitor(StrictModel):
    """Exact capacitor pin mapping eligible to decouple one supply pin."""

    reference: Identifier
    footprint: NonEmptyText
    supply_pad: Reference
    return_pad: Reference

    @model_validator(mode="after")
    def exact_capacitor_pads(self) -> PcbDecouplingCapacitor:
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in (self.supply_pad, self.return_pad)):
            raise ValueError("Decoupling capacitor pads must belong to the declared component")
        if self.supply_pad.casefold() == self.return_pad.casefold():
            raise ValueError("Decoupling capacitor supply and return pads must differ")
        return self


class PcbDecouplingRequirement(StrictModel):
    """Project-reviewed IC power/return pin and candidate capacitor placement rule."""

    id: Identifier
    basis: NonEmptyText
    ic_reference: Identifier
    ic_footprint: NonEmptyText
    supply_pad: Reference
    return_pad: Reference
    supply_net: NetName
    return_net: NetName
    capacitors: Annotated[tuple[PcbDecouplingCapacitor, ...], Field(min_length=1)]
    selection: Literal["any", "all"] = "any"
    max_distance_um: PositiveCount | None = None
    max_return_via_distance_um: PositiveCount | None = None

    @model_validator(mode="after")
    def exact_supply_mapping(self) -> PcbDecouplingRequirement:
        prefix = f"{self.ic_reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in (self.supply_pad, self.return_pad)):
            raise ValueError("Decoupling IC pads must belong to the declared component")
        if self.supply_pad.casefold() == self.return_pad.casefold():
            raise ValueError("Decoupling IC supply and return pads must differ")
        if self.supply_net.casefold() == self.return_net.casefold():
            raise ValueError("Decoupling supply and return nets must differ")
        if len({item.reference.casefold() for item in self.capacitors}) != len(self.capacitors):
            raise ValueError("A decoupling requirement cannot repeat a capacitor reference")
        return self


class PcbDecouplingMap(StrictModel):
    """Explicit per-project PCB decoupling scopes; no universal distance is assumed."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbDecouplingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_supply_pins(self) -> PcbDecouplingMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB decoupling requirement IDs must be unique")
        supply_pads = [item.supply_pad.casefold() for item in self.requirements]
        if len(set(supply_pads)) != len(supply_pads):
            raise ValueError("An IC supply pad can belong to only one decoupling requirement")
        return self


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
