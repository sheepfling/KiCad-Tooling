"""Typed project contracts and reports for PCB keepout coverage."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NativePcbUuid,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)


class PcbKeepoutRequirement(StrictModel):
    """Reviewed identity and exact native signature for one PCB keepout rule area."""

    id: Identifier
    basis: NonEmptyText
    name: NonEmptyText
    geometry_sha256: Digest
    layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    forbids_tracks: bool
    forbids_vias: bool
    forbids_pads: bool
    forbids_zone_fills: bool
    forbids_footprints: bool

    @model_validator(mode="after")
    def unique_layers(self) -> PcbKeepoutRequirement:
        if len({item.casefold() for item in self.layers}) != len(self.layers):
            raise ValueError("PCB keepout requirement layers must be unique")
        return self


class PcbKeepoutMap(StrictModel):
    """Project-owned signatures for reviewed copper keepout rule areas."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbKeepoutRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_keepouts(self) -> PcbKeepoutMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB keepout requirement IDs must be unique")
        if len({item.name.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A named PCB keepout can be mapped only once")
        return self


class PcbKeepoutCoverageEntry(StrictModel):
    """Comparison between one reviewed keepout signature and a native rule area."""

    id: Identifier
    basis: NonEmptyText
    name: NonEmptyText
    expected_geometry_sha256: Digest
    observed_uuid: NativePcbUuid | None = None
    observed_geometry_sha256: Digest | None = None
    expected_layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    observed_layers: tuple[NonEmptyText, ...] = ()
    expected_forbids_tracks: bool
    expected_forbids_vias: bool
    expected_forbids_pads: bool
    expected_forbids_zone_fills: bool
    expected_forbids_footprints: bool
    observed_forbids_tracks: bool | None = None
    observed_forbids_vias: bool | None = None
    observed_forbids_pads: bool | None = None
    observed_forbids_zone_fills: bool | None = None
    observed_forbids_footprints: bool | None = None
    status: Literal["COMPLETE", "INCOMPLETE"]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def status_matches_observation(self) -> PcbKeepoutCoverageEntry:
        observed_flags = (
            self.observed_forbids_tracks,
            self.observed_forbids_vias,
            self.observed_forbids_pads,
            self.observed_forbids_zone_fills,
            self.observed_forbids_footprints,
        )
        if self.status == "COMPLETE":
            if self.issues or any(item is None for item in observed_flags):
                raise ValueError("Complete PCB keepout coverage needs full matching evidence")
            expected_layers = {item.casefold() for item in self.expected_layers}
            observed_layers = {item.casefold() for item in self.observed_layers}
            expected_flags = (
                self.expected_forbids_tracks,
                self.expected_forbids_vias,
                self.expected_forbids_pads,
                self.expected_forbids_zone_fills,
                self.expected_forbids_footprints,
            )
            if (
                self.observed_geometry_sha256 != self.expected_geometry_sha256
                or observed_layers != expected_layers
                or observed_flags != expected_flags
            ):
                raise ValueError("Complete PCB keepout coverage must match its exact signature")
        elif not self.issues:
            raise ValueError("Incomplete PCB keepout coverage must explain its gap")
        return self


class PcbKeepoutCoverageReport(StrictModel):
    """Source-bound comparison of reviewed keepout signatures with native rule areas."""

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
    entries: tuple[PcbKeepoutCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbKeepoutCoverageReport:
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
            raise ValueError("Scanned PCB keepout evidence must bind all source and tool inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned PCB keepout coverage must contain every mapped area")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("PCB keepout report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB keepout coverage must explain its evidence gap")
        return self
