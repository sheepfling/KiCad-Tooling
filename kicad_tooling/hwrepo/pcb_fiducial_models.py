"""Typed project requirements and source-bound evidence for board fiducials."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NonEmptyText,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)

PcbFiducialSide = Literal["front", "back", "either"]
PcbFiducialMode = Literal["review", "block", "off"]
PcbFiducialSnapshotSchema = Literal[
    "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22"
]


class PcbFiducialRequirement(StrictModel):
    """One project-authored minimum for board-level fiducial placements."""

    id: Identifier
    basis: NonEmptyText
    minimum_count: PositiveCount
    accepted_footprints: tuple[NonEmptyText, ...] = Field(min_length=1)
    side: PcbFiducialSide = "either"

    @model_validator(mode="after")
    def unique_footprint_identities(self) -> PcbFiducialRequirement:
        keys = [item.strip().casefold() for item in self.accepted_footprints]
        if any(not item for item in keys) or len(keys) != len(set(keys)):
            raise ValueError("Accepted fiducial footprints must be nonempty and unique")
        return self


class PcbFiducialMap(StrictModel):
    """Explicit board-level fiducial-count requirements; panel data is out of scope."""

    schema_version: Literal["1"] = "1"
    requirements: tuple[PcbFiducialRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_requirement_ids(self) -> PcbFiducialMap:
        keys = [item.id.casefold() for item in self.requirements]
        if len(keys) != len(set(keys)):
            raise ValueError("PCB fiducial requirement IDs must be unique")
        return self


class PcbFiducialObservation(StrictModel):
    """One fitted native board footprint matching an authored fiducial identity."""

    reference: Identifier
    footprint: NonEmptyText
    side: Literal["F.Cu", "B.Cu"]
    position_nm: tuple[int, int]


class PcbFiducialCoverageEntry(StrictModel):
    """Count and identity evidence for one authored board-side requirement."""

    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    basis: NonEmptyText
    minimum_count: PositiveCount
    accepted_footprints: tuple[NonEmptyText, ...]
    side: PcbFiducialSide
    observed_count: int = Field(ge=0)
    observations: tuple[PcbFiducialObservation, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def consistent_count(self) -> PcbFiducialCoverageEntry:
        references = [item.reference.casefold() for item in self.observations]
        if len(references) != len(set(references)):
            raise ValueError("A native fiducial footprint cannot count twice for one requirement")
        if self.observed_count != len(self.observations):
            raise ValueError("Fiducial count must match its native footprint observations")
        enough = self.observed_count >= self.minimum_count
        if self.status == "COMPLETE" and (not enough or self.issues):
            raise ValueError("Complete fiducial coverage must meet its minimum without issues")
        if self.status == "INCOMPLETE" and enough and not self.issues:
            raise ValueError("Incomplete fiducial coverage must explain a missing minimum")
        return self


class PcbFiducialCoverageReport(StrictModel):
    """Coverage state bound to one exact native PCB snapshot and authored map."""

    status: Literal["NOT_REQUESTED", "DISABLED", "BLOCKED", "COMPLETE", "INCOMPLETE"] = (
        "NOT_REQUESTED"
    )
    mode: PcbFiducialMode | None = None
    map_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    snapshot_schema: PcbFiducialSnapshotSchema | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    probe_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    entries: tuple[PcbFiducialCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_source_receipt(self) -> PcbFiducialCoverageReport:
        ids = [item.id.casefold() for item in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("PCB fiducial report requirement IDs must be unique")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries or self.issue is not None:
                raise ValueError("Scanned fiducial coverage needs entries and no issue")
            if any(
                value is None
                for value in (
                    self.mode,
                    self.map_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.snapshot_path,
                    self.snapshot_sha256,
                    self.snapshot_schema,
                    self.kicad_version,
                    self.image,
                    self.probe_sha256,
                    self.netlist_sha256,
                )
            ):
                raise ValueError("Scanned fiducial coverage needs complete source identity")
            if self.mode == "off":
                raise ValueError("Disabled fiducial policy cannot contain scanned coverage")
            all_complete = all(item.status == "COMPLETE" for item in self.entries)
            if (self.status == "COMPLETE") != all_complete:
                raise ValueError("Fiducial report status must match its requirement entries")
        elif self.status == "BLOCKED":
            if self.mode == "off" or self.issue is None or self.entries:
                raise ValueError("Blocked fiducial coverage needs an active mode and issue")
        elif self.status == "DISABLED":
            if self.mode != "off" or self.issue is not None or self.entries:
                raise ValueError("Disabled fiducial coverage must have off mode and no evidence")
        elif (
            any(
                value is not None
                for value in (
                    self.mode,
                    self.map_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.snapshot_path,
                    self.snapshot_sha256,
                    self.snapshot_schema,
                    self.kicad_version,
                    self.image,
                    self.probe_sha256,
                    self.netlist_sha256,
                    self.issue,
                )
            )
            or self.entries
        ):
            raise ValueError("Unrequested fiducial coverage cannot contain evidence")
        return self
