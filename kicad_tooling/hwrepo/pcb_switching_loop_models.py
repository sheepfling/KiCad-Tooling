"""Typed project contracts and source-bound reports for PCB switching-loop checks."""

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


class PcbSwitchingLoopPad(StrictModel):
    """One exact project-mapped PCB pad in a switching-current review."""

    pad: Reference
    footprint: NonEmptyText
    net: NetName

    @model_validator(mode="after")
    def exact_switching_loop_pad(self) -> PcbSwitchingLoopPad:
        if self.pad.count(".") != 1:
            raise ValueError("Switching-loop pads must use an exact reference.pad number")
        return self


class PcbSwitchingLoopEdge(StrictModel):
    """One authored edge role between adjacent pads in a switching loop."""

    from_pad: Reference
    to_pad: Reference
    kind: Literal["trace", "component", "plane"]
    net: NetName | None = None
    layers: tuple[NonEmptyText, ...] = ()
    component_reference: Identifier | None = None
    plane_layer: NonEmptyText | None = None

    @model_validator(mode="after")
    def exact_edge_role(self) -> PcbSwitchingLoopEdge:
        if self.from_pad.casefold() == self.to_pad.casefold():
            raise ValueError("A switching-loop edge must join two distinct pads")
        if self.kind == "trace":
            if self.net is None or not self.layers:
                raise ValueError("A trace edge needs an exact net and copper-layer scope")
            if self.component_reference is not None or self.plane_layer is not None:
                raise ValueError("A trace edge cannot declare a component or plane role")
            if len({item.casefold() for item in self.layers}) != len(self.layers):
                raise ValueError("A trace edge cannot repeat a copper layer")
        elif self.kind == "component":
            if self.component_reference is None:
                raise ValueError("A component edge needs its exact component reference")
            if (
                self.from_pad.split(".", 1)[0].casefold() != self.component_reference.casefold()
                or self.to_pad.split(".", 1)[0].casefold() != self.component_reference.casefold()
            ):
                raise ValueError("A component edge must join pads on its declared component")
            if self.net is not None or self.layers or self.plane_layer is not None:
                raise ValueError("A component edge cannot declare trace or plane evidence")
        else:
            if self.net is None or self.plane_layer is None:
                raise ValueError("A plane edge needs an exact net and copper layer")
            if self.layers or self.component_reference is not None:
                raise ValueError("A plane edge cannot declare trace-layer or component evidence")
        return self


class PcbSwitchingLoopRequirement(StrictModel):
    """Project-authored switching-loop pad order and return-plane endpoints."""

    id: Identifier
    basis: NonEmptyText
    loop_pads: Annotated[tuple[PcbSwitchingLoopPad, ...], Field(min_length=3)]
    return_net: NetName
    return_plane_layer: NonEmptyText
    return_plane_pads: Annotated[tuple[PcbSwitchingLoopPad, ...], Field(min_length=2)]
    maximum_area_um2: PositiveCount | None = None
    route_edges: tuple[PcbSwitchingLoopEdge, ...] = ()

    @model_validator(mode="after")
    def exact_switching_loop_mapping(self) -> PcbSwitchingLoopRequirement:
        loop_names = [item.pad.casefold() for item in self.loop_pads]
        if len(set(loop_names)) != len(loop_names):
            raise ValueError("A switching-loop pad order cannot repeat a pad")
        plane_names = [item.pad.casefold() for item in self.return_plane_pads]
        if len(set(plane_names)) != len(plane_names):
            raise ValueError("A switching return-plane mapping cannot repeat a pad")
        if any(
            item.net.casefold() != self.return_net.casefold() for item in self.return_plane_pads
        ):
            raise ValueError("Every mapped return-plane pad must use the declared return net")
        loop_pads = {item.pad.casefold(): item for item in self.loop_pads}
        if any(loop_pads.get(item.pad.casefold()) != item for item in self.return_plane_pads):
            raise ValueError("Every return-plane endpoint must match a pad in the ordered loop map")
        if self.route_edges:
            if len(self.route_edges) != len(self.loop_pads):
                raise ValueError("A switching-loop edge map must cover every ordered pad edge")
            for index, edge in enumerate(self.route_edges):
                source = self.loop_pads[index]
                destination = self.loop_pads[(index + 1) % len(self.loop_pads)]
                if (
                    edge.from_pad.casefold() != source.pad.casefold()
                    or edge.to_pad.casefold() != destination.pad.casefold()
                ):
                    raise ValueError("Switching-loop edges must follow the exact ordered pad cycle")
                if edge.kind in {"trace", "plane"}:
                    if edge.net is None:
                        raise ValueError("A trace or plane edge needs an exact net")
                    if (
                        source.net.casefold() != edge.net.casefold()
                        or destination.net.casefold() != edge.net.casefold()
                    ):
                        raise ValueError(
                            "A trace or plane edge must match both endpoint pad net assignments"
                        )
                if edge.kind == "component" and source.footprint != destination.footprint:
                    raise ValueError("A component edge's endpoint pads must use the same footprint")
        return self


class PcbSwitchingLoopMap(StrictModel):
    """Opt-in project map for pad-center loop proxies and return-plane checks."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbSwitchingLoopRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_switching_loop_ids(self) -> PcbSwitchingLoopMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB switching-loop requirement IDs must be unique")
        return self


class PcbSwitchingLoopRouteEdgeCoverage(StrictModel):
    """Resolved track evidence or an explicit topology transition and its native zone."""

    edge_index: NonNegativeCount
    from_pad: Reference
    to_pad: Reference
    kind: Literal["trace", "component", "plane"]
    status: Literal["RESOLVED", "DECLARED", "INCOMPLETE"]
    track_uuids: tuple[NativePcbUuid, ...] = ()
    vertices_nm: tuple[tuple[int, int], ...] = ()
    length_nm: NonNegativeCount | None = None
    plane_zone_uuid: NativePcbUuid | None = None
    plane_island_index: NonNegativeCount | None = None
    plane_island_area_twice_nm2: NonNegativeCount | None = None
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def exact_route_edge_state(self) -> PcbSwitchingLoopRouteEdgeCoverage:
        if self.status == "RESOLVED":
            if self.kind != "trace" or not self.track_uuids or len(self.vertices_nm) < 2:
                raise ValueError("A resolved trace edge needs track IDs and route vertices")
            if (
                self.length_nm is None
                or len(self.vertices_nm) != len(self.track_uuids) + 1
                or self.issue is not None
                or self.plane_zone_uuid is not None
                or self.plane_island_index is not None
                or self.plane_island_area_twice_nm2 is not None
            ):
                raise ValueError(
                    "A resolved trace edge needs a length, one more vertex than tracks, and no issue"
                )
        elif self.status == "DECLARED":
            if (
                self.kind == "trace"
                or self.track_uuids
                or self.vertices_nm
                or self.length_nm is not None
            ):
                raise ValueError("Only component and plane edges can be declared without geometry")
            if self.issue is None:
                raise ValueError("A declared edge must explain its geometry limitation")
            if self.kind == "plane":
                if (self.plane_zone_uuid is None) != (self.plane_island_index is None):
                    raise ValueError("A declared plane edge needs both zone and island identities")
                if self.plane_zone_uuid is None and self.plane_island_area_twice_nm2 is not None:
                    raise ValueError("A plane-island area needs an exact zone and island identity")
                if (
                    self.plane_island_area_twice_nm2 is not None
                    and self.plane_island_area_twice_nm2 == 0
                ):
                    raise ValueError("A measured plane-island contour area must be positive")
            elif any(
                value is not None
                for value in (
                    self.plane_zone_uuid,
                    self.plane_island_index,
                    self.plane_island_area_twice_nm2,
                )
            ):
                raise ValueError("Component edges cannot carry plane-island evidence")
        else:
            if self.issue is None:
                raise ValueError("An incomplete route edge must explain the evidence gap")
            if self.kind == "plane":
                if (self.plane_zone_uuid is None) != (self.plane_island_index is None):
                    raise ValueError(
                        "An incomplete plane edge needs both zone and island identities"
                    )
                if self.plane_zone_uuid is None and self.plane_island_area_twice_nm2 is not None:
                    raise ValueError("A plane-island area needs an exact zone and island identity")
                if (
                    self.plane_island_area_twice_nm2 is not None
                    and self.plane_island_area_twice_nm2 == 0
                ):
                    raise ValueError("A measured plane-island contour area must be positive")
            elif any(
                value is not None
                for value in (
                    self.plane_zone_uuid,
                    self.plane_island_index,
                    self.plane_island_area_twice_nm2,
                )
            ):
                raise ValueError("Only plane edges can carry plane-island evidence")
        if len({item.casefold() for item in self.track_uuids}) != len(self.track_uuids):
            raise ValueError("A route edge cannot repeat a native track identity")
        return self


class PcbSwitchingLoopCoverageEntry(StrictModel):
    id: Identifier
    status: Literal["COMPLETE", "INCOMPLETE"]
    basis: NonEmptyText
    loop_pads: tuple[Reference, ...]
    loop_area_twice_nm2: NonNegativeCount | None
    maximum_area_um2: PositiveCount | None
    area_exceeds_limit: bool | None
    return_net: NetName
    return_plane_layer: NonEmptyText
    return_plane_pads: tuple[Reference, ...]
    return_plane_status: Literal["CONNECTED", "SPLIT", "UNOBSERVED", "UNSUPPORTED", "AMBIGUOUS"]
    return_zone_uuid: NonEmptyText | None = None
    return_island_index: NonNegativeCount | None = None
    route_status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE"] = "NOT_REQUESTED"
    route_edges: tuple[PcbSwitchingLoopRouteEdgeCoverage, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def exact_area_and_plane_status(self) -> PcbSwitchingLoopCoverageEntry:
        if self.loop_area_twice_nm2 is None and self.area_exceeds_limit is not None:
            raise ValueError("An unavailable switching-loop area cannot have a limit result")
        if self.loop_area_twice_nm2 is not None and self.maximum_area_um2 is None:
            if self.area_exceeds_limit is not None:
                raise ValueError("An unbounded switching-loop area cannot have a limit result")
        elif self.loop_area_twice_nm2 is not None and self.maximum_area_um2 is not None:
            expected = self.loop_area_twice_nm2 > 2 * self.maximum_area_um2 * 1_000_000
            if self.area_exceeds_limit != expected:
                raise ValueError("Switching-loop area result does not match the exact limit")
        if self.return_plane_status == "CONNECTED":
            if self.return_zone_uuid is None or self.return_island_index is None:
                raise ValueError("Connected return-plane evidence needs a zone and island")
        elif self.return_zone_uuid is not None or self.return_island_index is not None:
            raise ValueError("Non-connected return-plane evidence cannot name a connected island")
        if self.route_status == "NOT_REQUESTED":
            if self.route_edges:
                raise ValueError("Unrequested route evidence cannot include mapped edges")
        else:
            if len(self.route_edges) != len(self.loop_pads):
                raise ValueError("Route coverage must report every edge in the ordered pad cycle")
            for index, route_edge in enumerate(self.route_edges):
                source = self.loop_pads[index]
                destination = self.loop_pads[(index + 1) % len(self.loop_pads)]
                if (
                    route_edge.edge_index != index
                    or route_edge.from_pad.casefold() != source.casefold()
                    or route_edge.to_pad.casefold() != destination.casefold()
                ):
                    raise ValueError("Route coverage edges must follow the ordered pad cycle")
            if self.route_status == "COMPLETE":
                if any(item.status != "RESOLVED" for item in self.route_edges):
                    raise ValueError("Complete route coverage needs every mapped edge resolved")
            elif not self.issues:
                raise ValueError("Incomplete route coverage needs a reported evidence gap")
        if self.status == "COMPLETE" and (
            self.loop_area_twice_nm2 is None
            or self.return_plane_status != "CONNECTED"
            or self.area_exceeds_limit is True
            or self.route_status == "INCOMPLETE"
        ):
            raise ValueError("Complete switching-loop coverage needs measured, acceptable geometry")
        if self.status == "INCOMPLETE" and not self.issues:
            raise ValueError("Incomplete switching-loop coverage must explain its gap")
        return self


class PcbSwitchingLoopCoverageReport(StrictModel):
    """Source-bound measurements for explicitly mapped switching loops."""

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
    entries: tuple[PcbSwitchingLoopCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_scanned(self) -> PcbSwitchingLoopCoverageReport:
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
            raise ValueError("Scanned switching-loop evidence must bind all source and tool inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned switching-loop coverage needs each mapped requirement")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("Switching-loop report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked switching-loop coverage must explain its evidence gap")
        return self
