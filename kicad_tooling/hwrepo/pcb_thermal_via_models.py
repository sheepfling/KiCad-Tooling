"""Project-authored PCB pad-via coverage contracts and retained measurements."""

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


class PcbThermalViaLayerRequirement(StrictModel):
    """Minimum native-connected via multiplicity for one authored layer span."""

    start_layer: NonEmptyText
    end_layer: NonEmptyText
    minimum_vias: PositiveCount

    @model_validator(mode="after")
    def distinct_layers(self) -> PcbThermalViaLayerRequirement:
        if self.start_layer.casefold() == self.end_layer.casefold():
            raise ValueError("A PCB via-span requirement must name two distinct copper layers")
        return self


class PcbThermalViaRequirement(StrictModel):
    """Exact thermal-pad identity and project-reviewed via geometry screen."""

    id: Identifier
    basis: NonEmptyText
    pad: Reference
    footprint: NonEmptyText
    net: NetName
    maximum_center_distance_um: PositiveCount
    required_layer_spans: Annotated[tuple[PcbThermalViaLayerRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_pad_scope(self) -> PcbThermalViaRequirement:
        if self.pad.count(".") != 1:
            raise ValueError("A PCB thermal-via requirement must name one exact reference and pad")
        if not self.required_layer_spans:
            raise ValueError("A PCB thermal-via requirement needs at least one layer span")
        spans = {
            frozenset((item.start_layer.casefold(), item.end_layer.casefold()))
            for item in self.required_layer_spans
        }
        if len(spans) != len(self.required_layer_spans):
            raise ValueError("A PCB thermal-via requirement cannot repeat a layer span")
        return self


class PcbThermalViaMap(StrictModel):
    """Opt-in thermal-pad via screens; counts and geometry do not model heat transfer."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbThermalViaRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_thermal_pad_scopes(self) -> PcbThermalViaMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB thermal-via requirement IDs must be unique")
        if len({item.pad.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A PCB thermal pad can appear in only one thermal-via requirement")
        return self


class PcbThermalViaMeasurement(StrictModel):
    """One relevant native via's distance and connectivity to the mapped pad component."""

    via_id: Digest
    net: NetName | None
    start_layer: NonEmptyText
    end_layer: NonEmptyText
    multiplicity: PositiveCount
    center_distance_squared_nm2: NonNegativeCount
    within_authored_radius: bool
    connected_to_pad_component: bool


class PcbThermalViaCoverageEntry(StrictModel):
    """Coverage result for one exact pad, footprint, net, radius, and layer-span contract."""

    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    basis: NonEmptyText
    pad: Reference
    expected_footprint: NonEmptyText
    observed_footprint: NonEmptyText | None
    expected_net: NetName
    observed_net: NetName | None
    fitted: bool
    maximum_center_distance_um: PositiveCount
    required_layer_spans: tuple[PcbThermalViaLayerRequirement, ...]
    measurements: tuple[PcbThermalViaMeasurement, ...]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_entries_explain_the_basis(self) -> PcbThermalViaCoverageEntry:
        if self.status == "COMPLETE" and self.issues:
            raise ValueError("Complete PCB thermal-via coverage cannot contain issues")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete PCB thermal-via coverage must explain its gap")
        if len({item.via_id for item in self.measurements}) != len(self.measurements):
            raise ValueError("PCB thermal-via measurements must have unique native identities")
        if any(
            item.connected_to_pad_component and item.net != self.observed_net
            for item in self.measurements
        ):
            raise ValueError(
                "A connected thermal-via measurement must match the pad's observed net"
            )
        radius_squared_nm2 = (self.maximum_center_distance_um * 1000) ** 2
        if any(
            item.within_authored_radius != (item.center_distance_squared_nm2 <= radius_squared_nm2)
            for item in self.measurements
        ):
            raise ValueError("Thermal-via radius flags must match the exact squared-distance limit")
        if self.status == "COMPLETE":
            if (
                not self.fitted
                or self.observed_footprint is None
                or self.observed_footprint.casefold() != self.expected_footprint.casefold()
                or self.observed_net is None
                or self.observed_net.casefold() != self.expected_net.casefold()
            ):
                raise ValueError("Complete thermal-via coverage must match its fitted pad identity")
            for span in self.required_layer_spans:
                count = sum(
                    item.multiplicity
                    for item in self.measurements
                    if item.connected_to_pad_component
                    and item.within_authored_radius
                    and {item.start_layer.casefold(), item.end_layer.casefold()}
                    == {span.start_layer.casefold(), span.end_layer.casefold()}
                )
                if count < span.minimum_vias:
                    raise ValueError("Complete thermal-via coverage must meet every via-span count")
        return self


class PcbThermalViaCoverageReport(StrictModel):
    """Source-bound via count and center-distance evidence, not thermal adequacy."""

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
    entries: tuple[PcbThermalViaCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbThermalViaCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and not self.entries:
            raise ValueError("Scanned PCB thermal-via coverage needs requirement entries")
        if self.status == "COMPLETE" and any(item.status != "COMPLETE" for item in self.entries):
            raise ValueError("Complete PCB thermal-via coverage cannot contain incomplete entries")
        if self.status == "INCOMPLETE" and all(item.status == "COMPLETE" for item in self.entries):
            raise ValueError("Incomplete PCB thermal-via coverage must contain an incomplete entry")
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
                "Scanned PCB thermal-via evidence must bind all sources and tool inputs"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB thermal-via coverage must explain its evidence gap")
        return self
