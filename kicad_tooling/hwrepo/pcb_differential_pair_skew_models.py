"""Typed reports for project-mapped native differential-pair route skew."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NativePcbUuid,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    Reference,
    RepositoryPath,
    StrictModel,
)


class PcbDifferentialPairRouteMeasurement(StrictModel):
    """Native ordered track-layer and length evidence for one authored pad path."""

    path_id: Identifier
    net: NetName
    from_pad: Reference
    to_pad: Reference
    status: Literal["RESOLVED", "INCOMPLETE"]
    track_uuids: tuple[NativePcbUuid, ...] = ()
    track_layers: tuple[NonEmptyText, ...] = ()
    length_nm: NonNegativeCount | None = None
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def route_measurement_state(self) -> PcbDifferentialPairRouteMeasurement:
        if self.status == "RESOLVED":
            if (
                not self.track_uuids
                or self.length_nm is None
                or self.issue is not None
                or (self.track_layers and len(self.track_layers) != len(self.track_uuids))
            ):
                raise ValueError("Resolved pair routes need tracks and a measured length")
        elif self.length_nm is not None or self.issue is None:
            raise ValueError("Incomplete pair routes need an issue and no length")
        return self


class PcbDifferentialPairRouteSkewEntry(StrictModel):
    """Measured member routes and the authored maximum skew for one bundle."""

    bundle_id: Identifier
    max_skew_nm: NonNegativeCount
    measured_skew_nm: NonNegativeCount | None = None
    status: Literal["WITHIN_LIMIT", "EXCEEDS_LIMIT", "INCOMPLETE"]
    paths: tuple[PcbDifferentialPairRouteMeasurement, ...] = Field(min_length=2)
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def exact_bundle_measurement(self) -> PcbDifferentialPairRouteSkewEntry:
        if len({item.path_id.casefold() for item in self.paths}) != len(self.paths):
            raise ValueError("A measured differential-pair bundle cannot repeat a path")
        unresolved = any(item.status != "RESOLVED" for item in self.paths)
        if self.status == "INCOMPLETE":
            if not unresolved or self.measured_skew_nm is not None:
                raise ValueError("An incomplete pair bundle needs unresolved paths and no skew")
            return self
        if unresolved or self.issue is not None or self.measured_skew_nm is None:
            raise ValueError("A measured pair bundle needs complete routes and one skew value")
        lengths = tuple(item.length_nm for item in self.paths)
        if any(value is None for value in lengths):
            raise ValueError("A resolved pair route must have a length")
        measured = max(value for value in lengths if value is not None) - min(
            value for value in lengths if value is not None
        )
        if measured != self.measured_skew_nm:
            raise ValueError("Pair-bundle skew must equal maximum minus minimum route length")
        if (self.status == "WITHIN_LIMIT") != (measured <= self.max_skew_nm):
            raise ValueError("Pair-bundle result must match its authored maximum skew")
        return self


class PcbDifferentialPairRouteSkewReport(StrictModel):
    """Source-bound route lengths measured against project-authored pair skew limits."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    source_inventory_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    command_path: RepositoryPath | None = None
    command_sha256: Digest | None = None
    probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    entries: tuple[PcbDifferentialPairRouteSkewEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def report_matches_entries(self) -> PcbDifferentialPairRouteSkewReport:
        if len({item.bundle_id.casefold() for item in self.entries}) != len(self.entries):
            raise ValueError("Differential-pair route-skew report cannot repeat bundle IDs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries or any(
                value is None
                for value in (
                    self.map_sha256,
                    self.source_inventory_sha256,
                    self.netlist_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.snapshot_path,
                    self.snapshot_sha256,
                    self.command_path,
                    self.command_sha256,
                    self.probe_sha256,
                    self.kicad_version,
                    self.image,
                )
            ):
                raise ValueError("Measured route-skew evidence must bind its map and sources")
            if self.mode not in {"review", "block"} or self.map_sha256 is None:
                raise ValueError(
                    "Measured route-skew evidence needs an active mode and mapped contract"
                )
            has_incomplete = any(item.status != "WITHIN_LIMIT" for item in self.entries)
            if (self.status == "INCOMPLETE") != has_incomplete:
                raise ValueError("Route-skew report status must match its bundle results")
        elif self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked route-skew coverage must explain the evidence gap")
        elif self.status == "DISABLED" and self.mode != "off":
            raise ValueError("Disabled route-skew coverage must use off mode")
        elif self.status == "NOT_REQUESTED" and self.entries:
            raise ValueError("Unrequested route-skew coverage cannot contain measured bundles")
        return self
