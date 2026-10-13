"""Project requirements and source-bound evidence for PCB protection paths."""

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


class PcbProtectionPathRequirement(StrictModel):
    """Project-reviewed connector-to-protector pad path and reference-via screen."""

    id: Identifier
    connector_reference: Identifier
    connector_footprint: NonEmptyText
    connector_signal_pad: Reference
    protection_reference: Identifier
    protection_footprint: NonEmptyText
    protection_signal_pad: Reference
    protection_reference_pad: Reference
    signal_net: NetName
    reference_net: NetName
    max_entry_distance_um: PositiveCount | None = None
    minimum_reference_vias: PositiveCount | None = None
    reference_via_radius_um: PositiveCount | None = None

    @model_validator(mode="after")
    def exact_protection_pad_mapping(self) -> PcbProtectionPathRequirement:
        if not self.connector_signal_pad.casefold().startswith(
            f"{self.connector_reference}.".casefold()
        ):
            raise ValueError("PCB protection connector pad must belong to its connector")
        prefix = f"{self.protection_reference}.".casefold()
        if any(
            not pad.casefold().startswith(prefix)
            for pad in (self.protection_signal_pad, self.protection_reference_pad)
        ):
            raise ValueError("PCB protection pads must belong to the declared device")
        if self.protection_signal_pad.casefold() == self.protection_reference_pad.casefold():
            raise ValueError("PCB protection signal and reference pads must differ")
        if self.signal_net.casefold() == self.reference_net.casefold():
            raise ValueError("PCB protection signal and reference nets must differ")
        if (self.minimum_reference_vias is None) != (self.reference_via_radius_um is None):
            raise ValueError(
                "PCB reference-via count and radius limits must be configured together"
            )
        if self.max_entry_distance_um is None and self.minimum_reference_vias is None:
            raise ValueError(
                "PCB protection path needs at least one project-authored geometry limit"
            )
        return self


class PcbProtectionPathMap(StrictModel):
    """Explicit PCB pads and project-selected limits for external protection paths."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbProtectionPathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_path_ids_and_endpoints(self) -> PcbProtectionPathMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB protection path IDs must be unique")
        endpoints = [
            (item.connector_signal_pad.casefold(), item.protection_signal_pad.casefold())
            for item in self.requirements
        ]
        if len(set(endpoints)) != len(endpoints):
            raise ValueError("PCB protection connector and signal-pad pairs must be unique")
        return self


class PcbProtectionPathEntry(StrictModel):
    """Native pad, component, and connected-via evidence for one protection path."""

    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    connector_signal_pad: Reference
    protection_signal_pad: Reference
    protection_reference_pad: Reference
    signal_net: NetName
    reference_net: NetName
    expected_connector_footprint: NonEmptyText
    observed_connector_footprint: NonEmptyText | None
    expected_protection_footprint: NonEmptyText
    observed_protection_signal_footprint: NonEmptyText | None
    observed_protection_reference_footprint: NonEmptyText | None
    observed_connector_signal_net: NetName | None
    observed_protection_signal_net: NetName | None
    observed_protection_reference_net: NetName | None
    connector_signal_fitted: bool | None
    protection_signal_fitted: bool | None
    protection_reference_fitted: bool | None
    native_signal_path_connected: bool
    connector_to_protection_distance_nm: NonNegativeCount | None
    connector_to_protection_distance_squared_nm2: NonNegativeCount | None
    connected_reference_via_count: NonNegativeCount
    reference_vias_within_radius: NonNegativeCount | None
    reference_via_radius_um: PositiveCount | None
    nearest_reference_via_id: Digest | None
    nearest_reference_via_distance_nm: NonNegativeCount | None
    max_entry_distance_um: PositiveCount | None
    minimum_reference_vias: PositiveCount | None
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_measured_distances(self) -> PcbProtectionPathEntry:
        if (self.connector_to_protection_distance_nm is None) != (
            self.connector_to_protection_distance_squared_nm2 is None
        ):
            raise ValueError("PCB protection entry distance fields must be present together")
        if (self.nearest_reference_via_id is None) != (
            self.nearest_reference_via_distance_nm is None
        ):
            raise ValueError("PCB protection via identity and distance must be present together")
        if self.minimum_reference_vias is None:
            if (
                self.reference_via_radius_um is not None
                or self.reference_vias_within_radius is not None
            ):
                raise ValueError("PCB protection via-radius evidence requires a configured minimum")
        elif self.reference_via_radius_um is None:
            raise ValueError("Configured PCB protection via minimum needs its authored radius")
        elif self.reference_vias_within_radius is None and not self.issues:
            raise ValueError("Complete PCB protection evidence needs a measured via-radius count")
        if self.status == "COMPLETE" and self.issues:
            raise ValueError("Complete PCB protection path cannot contain issues")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete PCB protection path must explain the evidence gap")
        return self


class PcbProtectionPathCoverageReport(StrictModel):
    """Source-bound native PCB evidence for configured external protection paths."""

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
    entries: tuple[PcbProtectionPathEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbProtectionPathCoverageReport:
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
            raise ValueError("Scanned PCB protection path evidence must bind all native sources")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB protection path evidence must explain the source gap")
        return self
