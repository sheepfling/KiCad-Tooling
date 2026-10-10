"""Typed contracts and source-bound reports for PCB RF antenna lint."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NativePcbUuid,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class PcbRfAntennaPolygon(StrictModel):
    """Project-authored footprint-local outline and holes for an antenna keepout."""

    outline_nm: Annotated[tuple[tuple[int, int], ...], Field(min_length=3)]
    holes_nm: tuple[Annotated[tuple[tuple[int, int], ...], Field(min_length=3)], ...] = ()

    @model_validator(mode="after")
    def valid_local_contours(self) -> PcbRfAntennaPolygon:
        for label, ring in (
            ("outline", self.outline_nm),
            *(("hole", hole) for hole in self.holes_nm),
        ):
            if len(set(ring)) != len(ring):
                raise ValueError(f"RF antenna keepout {label} cannot repeat vertices")
            area_twice = sum(
                first[0] * ring[(index + 1) % len(ring)][1]
                - ring[(index + 1) % len(ring)][0] * first[1]
                for index, first in enumerate(ring)
            )
            if area_twice == 0:
                raise ValueError(f"RF antenna keepout {label} must enclose nonzero area")
        if len({_canonical_rf_ring(hole) for hole in self.holes_nm}) != len(self.holes_nm):
            raise ValueError("RF antenna keepout holes must be unique")
        return self


def _canonical_rf_ring(ring: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    forward = tuple(ring)
    reverse = tuple(reversed(ring))
    return min(
        candidate[index:] + candidate[:index]
        for candidate in (forward, reverse)
        for index in range(len(candidate))
    )


def _canonical_rf_polygon(
    polygon: PcbRfAntennaPolygon,
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[tuple[int, int], ...], ...]]:
    return (
        _canonical_rf_ring(polygon.outline_nm),
        tuple(sorted(_canonical_rf_ring(hole) for hole in polygon.holes_nm)),
    )


class PcbRfAntennaKeepout(StrictModel):
    """Exact placement-relative rule-area requirement for an onboard antenna."""

    name: NonEmptyText
    local_polygons: Annotated[tuple[PcbRfAntennaPolygon, ...], Field(min_length=1)]
    layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    forbids_tracks: bool
    forbids_vias: bool
    forbids_pads: bool
    forbids_zone_fills: bool
    forbids_footprints: bool

    @model_validator(mode="after")
    def unique_keepout_layers_and_polygons(self) -> PcbRfAntennaKeepout:
        if len({item.casefold() for item in self.layers}) != len(self.layers):
            raise ValueError("RF antenna keepout layers must be unique")
        if len({_canonical_rf_polygon(item) for item in self.local_polygons}) != len(
            self.local_polygons
        ):
            raise ValueError("RF antenna keepout polygons must be unique")
        return self


class PcbRfModuleAntennaRequirement(StrictModel):
    """Independent identity, population, feed, and antenna disposition requirement."""

    id: Identifier
    basis: NonEmptyText
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier | None = None
    disposition: Literal["onboard_antenna", "external_antenna", "dnp"]
    rf_feed_pad: Reference | None = None
    rf_feed_net: NetName | None = None
    keepout: PcbRfAntennaKeepout | None = None

    @model_validator(mode="after")
    def coherent_antenna_disposition(self) -> PcbRfModuleAntennaRequirement:
        if (self.rf_feed_pad is None) != (self.rf_feed_net is None):
            raise ValueError("RF feed pad and net must be authored together")
        if self.rf_feed_pad is not None and (
            self.rf_feed_pad.count(".") != 1
            or self.rf_feed_pad.split(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("RF feed pad must be an exact pad on the mapped module reference")
        if self.disposition == "onboard_antenna":
            if self.rf_feed_pad is None or self.keepout is None:
                raise ValueError(
                    "An onboard-antenna requirement needs its RF feed and placement keepout"
                )
        elif self.disposition == "external_antenna":
            if self.rf_feed_pad is None or self.keepout is not None:
                raise ValueError(
                    "An external-antenna requirement needs its RF feed and no onboard keepout"
                )
        elif self.rf_feed_pad is not None or self.keepout is not None:
            raise ValueError("A DNP RF module cannot require a fitted RF feed or keepout")
        return self


class PcbRfModuleAntennaMap(StrictModel):
    """Reviewed RF module dispositions and footprint-relative antenna clearances."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbRfModuleAntennaRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_module_requirements(self) -> PcbRfModuleAntennaMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("RF module antenna requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("An RF module reference can be mapped only once")
        if len(
            {item.keepout.name.casefold() for item in self.requirements if item.keepout is not None}
        ) != sum(item.keepout is not None for item in self.requirements):
            raise ValueError("An RF antenna keepout name can be mapped only once")
        return self


class PcbRfModuleAntennaCoverageEntry(StrictModel):
    """Schematic and PCB identity, fitted state, feed, and keepout comparison."""

    id: Identifier
    basis: NonEmptyText
    reference: Identifier
    disposition: Literal["onboard_antenna", "external_antenna", "dnp"]
    expected_symbol: NonEmptyText
    observed_symbol: NonEmptyText | None = None
    expected_footprint: NonEmptyText
    observed_schematic_footprint: NonEmptyText | None = None
    observed_board_footprint: NonEmptyText | None = None
    expected_part_id: Identifier | None = None
    observed_part_id: Identifier | None = None
    expected_dnp: bool
    observed_schematic_dnp: bool | None = None
    observed_board_dnp: bool | None = None
    rf_feed_pad: Reference | None = None
    expected_rf_feed_net: NetName | None = None
    observed_schematic_rf_feed_nets: tuple[NetName, ...] = ()
    observed_board_rf_feed_net: NetName | None = None
    expected_keepout_name: NonEmptyText | None = None
    observed_keepout_uuids: tuple[NativePcbUuid, ...] = ()
    expected_geometry_sha256: Digest | None = None
    observed_geometry_sha256: Digest | None = None
    expected_layers: tuple[NonEmptyText, ...] = ()
    observed_layers: tuple[NonEmptyText, ...] = ()
    expected_forbids_tracks: bool | None = None
    expected_forbids_vias: bool | None = None
    expected_forbids_pads: bool | None = None
    expected_forbids_zone_fills: bool | None = None
    expected_forbids_footprints: bool | None = None
    observed_forbids_tracks: bool | None = None
    observed_forbids_vias: bool | None = None
    observed_forbids_pads: bool | None = None
    observed_forbids_zone_fills: bool | None = None
    observed_forbids_footprints: bool | None = None
    status: Literal["COMPLETE", "INCOMPLETE"]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_entry_has_no_open_evidence(self) -> PcbRfModuleAntennaCoverageEntry:
        if self.status == "COMPLETE" and self.issues:
            raise ValueError("Complete RF module antenna coverage cannot have issues")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete RF module antenna coverage must explain its gap")
        if self.status == "COMPLETE":
            if (
                self.observed_symbol != self.expected_symbol
                or self.observed_schematic_footprint != self.expected_footprint
                or self.observed_board_footprint != self.expected_footprint
                or self.observed_schematic_dnp != self.expected_dnp
                or self.observed_board_dnp != self.expected_dnp
                or (
                    self.expected_part_id is not None
                    and self.observed_part_id != self.expected_part_id
                )
            ):
                raise ValueError("Complete RF module coverage must match exact source identities")
            if self.expected_dnp:
                if (
                    self.rf_feed_pad is not None
                    or self.expected_rf_feed_net is not None
                    or self.observed_schematic_rf_feed_nets
                    or self.observed_board_rf_feed_net is not None
                    or self.expected_keepout_name is not None
                ):
                    raise ValueError(
                        "Complete DNP coverage cannot require a fitted feed or keepout"
                    )
            elif (
                self.rf_feed_pad is None
                or self.expected_rf_feed_net is None
                or self.observed_schematic_rf_feed_nets != (self.expected_rf_feed_net,)
                or self.observed_board_rf_feed_net != self.expected_rf_feed_net
            ):
                raise ValueError(
                    "Complete fitted RF module coverage must match its feed pad and net"
                )
            if self.disposition == "onboard_antenna":
                expected_flags = (
                    self.expected_forbids_tracks,
                    self.expected_forbids_vias,
                    self.expected_forbids_pads,
                    self.expected_forbids_zone_fills,
                    self.expected_forbids_footprints,
                )
                observed_flags = (
                    self.observed_forbids_tracks,
                    self.observed_forbids_vias,
                    self.observed_forbids_pads,
                    self.observed_forbids_zone_fills,
                    self.observed_forbids_footprints,
                )
                if (
                    self.expected_keepout_name is None
                    or len(self.observed_keepout_uuids) != 1
                    or self.expected_geometry_sha256 is None
                    or self.observed_geometry_sha256 != self.expected_geometry_sha256
                    or {item.casefold() for item in self.expected_layers}
                    != {item.casefold() for item in self.observed_layers}
                    or any(item is None for item in expected_flags)
                    or observed_flags != expected_flags
                ):
                    raise ValueError(
                        "Complete onboard antenna coverage must match exact native keepout evidence"
                    )
        if self.disposition == "onboard_antenna" and self.expected_keepout_name is None:
            raise ValueError("Onboard-antenna coverage needs its mapped keepout name")
        if self.disposition == "external_antenna" and self.expected_keepout_name is not None:
            raise ValueError("External-antenna coverage cannot require an onboard keepout")
        if self.disposition == "dnp" and not self.expected_dnp:
            raise ValueError("DNP disposition must expect an unpopulated module")
        return self


class PcbRfModuleAntennaCoverageReport(StrictModel):
    """Source-bound audit of mapped RF modules against native PCB placement evidence."""

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
    entries: tuple[PcbRfModuleAntennaCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbRfModuleAntennaCoverageReport:
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
            raise ValueError("Scanned RF module coverage must bind all source and tool inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned RF module coverage must include every mapped module")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("RF module report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked RF module coverage must explain its evidence gap")
        return self
