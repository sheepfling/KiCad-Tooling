"""Typed source-bound models for PCB track-width contracts and reports."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)


class PcbTrackWidthRequirement(StrictModel):
    """Project-authored minimum width screen for one exact PCB net."""

    id: Identifier
    basis: NonEmptyText
    net: NetName
    minimum_width_um: PositiveCount


class PcbTrackWidthMap(StrictModel):
    """Per-project track-width screens; values are not generic ampacity ratings."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbTrackWidthRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_net_requirements(self) -> PcbTrackWidthMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB track-width requirement IDs must be unique")
        if len({item.net.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A PCB net can have only one mapped minimum track width")
        return self


class PcbTrackWidthMeasurement(StrictModel):
    """Exact native track segment width compared with a project-authored screen."""

    track_uuid: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    layer: NonEmptyText
    width_nm: PositiveCount
    minimum_width_um: PositiveCount
    start_nm: tuple[int, int]
    end_nm: tuple[int, int]
    below_minimum: bool

    @model_validator(mode="after")
    def exact_threshold_result(self) -> PcbTrackWidthMeasurement:
        if self.below_minimum != (self.width_nm < self.minimum_width_um * 1000):
            raise ValueError("PCB track-width result does not match the exact nanometer boundary")
        return self


class PcbTrackWidthCoverageEntry(StrictModel):
    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    basis: NonEmptyText
    net: NetName
    minimum_width_um: PositiveCount
    tracks: tuple[PcbTrackWidthMeasurement, ...]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def coverage_has_measurements_or_issue(self) -> PcbTrackWidthCoverageEntry:
        if self.status == "COMPLETE" and not self.tracks:
            raise ValueError("Complete PCB track-width coverage needs measured segments")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete PCB track-width coverage must explain its gap")
        if any(item.minimum_width_um != self.minimum_width_um for item in self.tracks):
            raise ValueError("PCB track measurements must use their entry's exact threshold")
        if len({item.track_uuid.casefold() for item in self.tracks}) != len(self.tracks):
            raise ValueError("PCB track-width entry repeats a native track identity")
        return self


class PcbTrackWidthCoverageReport(StrictModel):
    """Native, source-bound measurements for explicit PCB track-width screens."""

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
    entries: tuple[PcbTrackWidthCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbTrackWidthCoverageReport:
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
            raise ValueError(
                "Scanned PCB track-width evidence must bind all source and tool inputs"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB track-width coverage must explain the evidence gap")
        return self
