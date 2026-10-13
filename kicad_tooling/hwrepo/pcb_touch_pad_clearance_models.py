"""Project requirements and source-bound records for touch-pad clearance lint."""

from __future__ import annotations

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
    Reference,
    RepositoryPath,
    StrictModel,
)


class PcbTouchPadClearanceRequirement(StrictModel):
    """Exact signal pad, reference-copper net, layer, and independent minimum gap."""

    id: Identifier
    pad: Reference
    expected_pad_net: NetName
    reference_net: NetName
    layer: NonEmptyText
    minimum_clearance_nm: PositiveCount

    @model_validator(mode="after")
    def exact_distinct_pad_and_nets(self) -> PcbTouchPadClearanceRequirement:
        if self.pad.count(".") != 1:
            raise ValueError("Touch-pad clearance must name one exact reference.pad")
        if self.expected_pad_net.casefold() == self.reference_net.casefold():
            raise ValueError("Touch-pad signal and reference copper nets must differ")
        return self


class PcbTouchPadClearanceMap(StrictModel):
    """Reviewed minimum copper separation requirements for exact signal pads."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbTouchPadClearanceRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_touch_pad_requirements(self) -> PcbTouchPadClearanceMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Touch-pad clearance requirement IDs must be unique")
        identities = {
            (item.pad.casefold(), item.layer.casefold(), item.reference_net.casefold())
            for item in self.requirements
        }
        if len(identities) != len(self.requirements):
            raise ValueError("Touch-pad clearance pad/layer/reference-net tuples must be unique")
        return self


class PcbTouchPadClearanceRequestSet(StrictModel):
    """Canonical native probe requests derived only from the authored clearance map."""

    schema_version: Literal["1"] = "1"
    requests: Annotated[tuple[PcbTouchPadClearanceRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_request_ids(self) -> PcbTouchPadClearanceRequestSet:
        if len({item.id.casefold() for item in self.requests}) != len(self.requests):
            raise ValueError("Native touch-pad probe request IDs must be unique")
        return self


class PcbTouchPadClearanceObservation(StrictModel):
    """Native measured gap from one exact pad shape to matching filled zone copper."""

    requirement_id: Identifier
    pad: Reference
    expected_pad_net: NetName
    observed_pad_net: NetName | None
    reference_net: NetName
    layer: NonEmptyText
    matching_zone_count: NonNegativeCount
    closest_zone_uuid: NativePcbUuid | None
    distance_nm: NonNegativeCount | None
    status: Literal[
        "MEASURED",
        "PAD_MISSING",
        "PAD_AMBIGUOUS",
        "PAD_LAYER_ABSENT",
        "UNSUPPORTED_LAYER",
        "NO_REFERENCE_ZONE",
        "NO_FILLED_REFERENCE_COPPER",
    ]

    @model_validator(mode="after")
    def observation_shape_matches_status(self) -> PcbTouchPadClearanceObservation:
        measured = self.status == "MEASURED"
        if measured != (self.distance_nm is not None and self.closest_zone_uuid is not None):
            raise ValueError(
                "Measured touch-pad clearance needs a distance and exact zone identity"
            )
        if measured and self.matching_zone_count == 0:
            raise ValueError("Measured touch-pad clearance needs at least one matching zone")
        if not measured and (self.distance_nm is not None or self.closest_zone_uuid is not None):
            raise ValueError("Unavailable touch-pad clearance cannot contain a measured distance")
        if self.status == "NO_REFERENCE_ZONE" and self.matching_zone_count != 0:
            raise ValueError("No-reference-zone observation must report a zero matching-zone count")
        if self.status == "NO_FILLED_REFERENCE_COPPER" and self.matching_zone_count == 0:
            raise ValueError("No-filled-copper observation must report matching zone definitions")
        if self.status in {"PAD_MISSING", "PAD_AMBIGUOUS"} and self.observed_pad_net is not None:
            raise ValueError("Missing or ambiguous touch pad cannot have one observed net")
        return self


class PcbTouchPadClearanceCoverageEntry(StrictModel):
    """Comparison of one independent clearance requirement with exact native evidence."""

    requirement_id: Identifier
    basis: NonEmptyText
    pad: Reference
    expected_pad_net: NetName
    schematic_pad_net: NetName | None
    observed_pad_net: NetName | None
    reference_net: NetName
    layer: NonEmptyText
    minimum_clearance_nm: PositiveCount
    measured_clearance_nm: NonNegativeCount | None
    closest_zone_uuid: NativePcbUuid | None
    status: Literal["COMPLETE", "INCOMPLETE"]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def clearance_evidence_is_coherent(self) -> PcbTouchPadClearanceCoverageEntry:
        if self.status == "COMPLETE":
            if self.issues or self.measured_clearance_nm is None or self.closest_zone_uuid is None:
                raise ValueError("Complete touch-pad coverage needs one unambiguous measurement")
            if (
                self.schematic_pad_net != self.expected_pad_net
                or self.observed_pad_net != self.expected_pad_net
            ):
                raise ValueError(
                    "Complete touch-pad coverage must match both authored and observed nets"
                )
        elif not self.issues:
            raise ValueError("Incomplete touch-pad coverage must explain its evidence gap")
        return self

    @property
    def violates_minimum_clearance(self) -> bool:
        """Return whether a complete measurement falls below the independent minimum."""
        return (
            self.measured_clearance_nm is not None
            and self.measured_clearance_nm < self.minimum_clearance_nm
        )


class PcbTouchPadClearanceCoverageReport(StrictModel):
    """Source-bound results for one project's exact touch-pad clearance map."""

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
    request_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    netlist_sha256: Digest | None = None
    requirement_count: PositiveCount | None = None
    entries: tuple[PcbTouchPadClearanceCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbTouchPadClearanceCoverageReport:
        required = (
            self.map_sha256,
            self.board_path,
            self.board_sha256,
            self.snapshot_path,
            self.snapshot_sha256,
            self.probe_sha256,
            self.request_sha256,
            self.kicad_version,
            self.image,
            self.netlist_sha256,
            self.requirement_count,
        )
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(item is None for item in required):
            raise ValueError("Scanned touch-pad coverage must bind its source, request, and tool")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned touch-pad coverage must include every mapped pad")
            if self.requirement_count != len(self.entries):
                raise ValueError(
                    "Touch-pad coverage must include every mapped requirement exactly once"
                )
            if len({item.requirement_id.casefold() for item in self.entries}) != len(self.entries):
                raise ValueError("Touch-pad coverage requirement IDs must be unique")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("Touch-pad report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked touch-pad coverage must explain its evidence gap")
        return self
