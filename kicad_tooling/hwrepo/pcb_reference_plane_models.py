"""Typed project contracts and source-bound reports for PCB reference-plane checks."""

from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NativePcbUuid,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)


class PcbReferencePlaneRequirement(StrictModel):
    """Project-authored centerline-coverage screen for one PCB signal net."""

    id: Identifier
    basis: NonEmptyText
    signal_net: NetName
    signal_layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    reference_net: NetName
    minimum_track_length_um: PositiveCount
    minimum_referenced_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    review_excluded_short_tracks: bool = False

    @model_validator(mode="after")
    def exact_reference_scope(self) -> PcbReferencePlaneRequirement:
        if self.signal_net.casefold() == self.reference_net.casefold():
            raise ValueError("PCB signal and reference-plane nets must be distinct")
        if len({item.casefold() for item in self.signal_layers}) != len(self.signal_layers):
            raise ValueError("PCB reference-plane screen cannot repeat a signal layer")
        return self


class PcbReferencePlaneMap(StrictModel):
    """Opt-in, project-scoped reference-plane centerline thresholds."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbReferencePlaneRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_reference_scopes(self) -> PcbReferencePlaneMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB reference-plane requirement IDs must be unique")
        scopes = [
            (item.signal_net.casefold(), layer.casefold())
            for item in self.requirements
            for layer in item.signal_layers
        ]
        if len(set(scopes)) != len(scopes):
            raise ValueError("A signal net and layer can appear in only one reference-plane screen")
        return self


class PcbReferencePlaneTrackMeasurement(StrictModel):
    """Centerline fraction over native filled reference copper for one track."""

    track_uuid: NativePcbUuid
    signal_layer: NonEmptyText
    reference_layer: NonEmptyText
    reference_zone_uuids: tuple[NativePcbUuid, ...]
    endpoint_via_ids: tuple[Digest, ...] = ()
    endpoint_via_ids_with_center_in_reference_holes: tuple[Digest, ...] = ()
    segment_length_nm: PositiveCount
    covered_fraction_numerator: NonNegativeCount
    covered_fraction_denominator: PositiveCount
    below_minimum: bool

    @model_validator(mode="after")
    def canonical_coverage_fraction(self) -> PcbReferencePlaneTrackMeasurement:
        if self.covered_fraction_numerator > self.covered_fraction_denominator:
            raise ValueError("PCB reference-plane coverage fraction cannot exceed one")
        fraction = Fraction(
            self.covered_fraction_numerator,
            self.covered_fraction_denominator,
        )
        if (
            fraction.numerator != self.covered_fraction_numerator
            or fraction.denominator != self.covered_fraction_denominator
        ):
            raise ValueError("PCB reference-plane coverage fraction must be reduced")
        if len({item.casefold() for item in self.reference_zone_uuids}) != len(
            self.reference_zone_uuids
        ):
            raise ValueError("PCB reference-plane measurement repeats a zone identity")
        endpoint_vias = {item.casefold() for item in self.endpoint_via_ids}
        hole_vias = {
            item.casefold() for item in self.endpoint_via_ids_with_center_in_reference_holes
        }
        if len(endpoint_vias) != len(self.endpoint_via_ids) or len(hole_vias) != len(
            self.endpoint_via_ids_with_center_in_reference_holes
        ):
            raise ValueError("PCB reference-plane measurement repeats an endpoint via")
        if not hole_vias <= endpoint_vias:
            raise ValueError("Reference-hole via context must name an observed track endpoint via")
        return self


class PcbReferencePlaneCoverageEntry(StrictModel):
    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    basis: NonEmptyText
    signal_net: NetName
    signal_layers: tuple[NonEmptyText, ...]
    reference_net: NetName
    minimum_track_length_um: PositiveCount
    minimum_referenced_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    review_excluded_short_tracks: bool = False
    tracks: tuple[PcbReferencePlaneTrackMeasurement, ...]
    excluded_short_track_uuids: tuple[NativePcbUuid, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def consistent_track_coverage(self) -> PcbReferencePlaneCoverageEntry:
        if self.status == "COMPLETE" and not self.tracks:
            raise ValueError("Complete reference-plane coverage needs measured segments")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete reference-plane coverage must explain its gap")
        track_ids = {
            (item.track_uuid.casefold(), item.reference_layer.casefold()) for item in self.tracks
        }
        excluded_ids = {item.casefold() for item in self.excluded_short_track_uuids}
        if len(track_ids) != len(self.tracks) or len(excluded_ids) != len(
            self.excluded_short_track_uuids
        ):
            raise ValueError("Reference-plane coverage cannot repeat a track and layer identity")
        if {track_id for track_id, _layer in track_ids} & excluded_ids:
            raise ValueError("A reference-plane track cannot be measured and excluded")
        if self.review_excluded_short_tracks and excluded_ids and self.status != "INCOMPLETE":
            raise ValueError("Reviewed short reference-plane tracks must leave coverage incomplete")
        minimum = Fraction(str(self.minimum_referenced_fraction))
        for item in self.tracks:
            if item.segment_length_nm < self.minimum_track_length_um * 1000:
                raise ValueError("Measured reference-plane tracks must meet the authored length")
            if not any(
                item.signal_layer.casefold() == layer.casefold() for layer in self.signal_layers
            ):
                raise ValueError("Reference-plane track layer is absent from its mapped scope")
            measured = Fraction(
                item.covered_fraction_numerator,
                item.covered_fraction_denominator,
            )
            if item.below_minimum != (measured < minimum):
                raise ValueError(
                    "Reference-plane result does not match its exact authored fraction"
                )
        return self


class PcbReferencePlaneCoverageReport(StrictModel):
    """Native, source-bound measurements for project-mapped PCB reference planes."""

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
    entries: tuple[PcbReferencePlaneCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbReferencePlaneCoverageReport:
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
                "Scanned PCB reference-plane evidence must bind all source and tool inputs"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB reference-plane coverage must explain the evidence gap")
        return self
