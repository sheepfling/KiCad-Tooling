"""Typed observations collected from a native KiCad PCB probe."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    Reference,
    StrictModel,
)


class PcbZoneIdentity(StrictModel):
    """Native KiCad identity for one copper zone on one board layer."""

    uuid: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    layer: NonEmptyText


class PcbZoneFilledIslandObservation(StrictModel):
    """Canonical integer-nanometer outline and holes for one filled zone island."""

    island_index: NonNegativeCount
    outline_nm: tuple[tuple[int, int], ...]
    holes_nm: tuple[tuple[tuple[int, int], ...], ...] = ()

    @model_validator(mode="after")
    def valid_zone_contours(self) -> PcbZoneFilledIslandObservation:
        for label, ring in (
            ("outline", self.outline_nm),
            *(("hole", hole) for hole in self.holes_nm),
        ):
            if len(ring) < 3 or len(set(ring)) < 3 or ring[0] == ring[-1]:
                raise ValueError(
                    f"Native PCB filled-island {label} needs three distinct open-ring vertices"
                )
            area_twice = sum(
                first[0] * ring[(index + 1) % len(ring)][1]
                - ring[(index + 1) % len(ring)][0] * first[1]
                for index, first in enumerate(ring)
            )
            if area_twice == 0:
                raise ValueError(f"Native PCB filled-island {label} has zero area")
        return self


class PcbRuleAreaPolygonObservation(StrictModel):
    """Canonical authored outline and holes for one native PCB rule area."""

    outline_nm: tuple[tuple[int, int], ...]
    holes_nm: tuple[tuple[tuple[int, int], ...], ...] = ()

    @model_validator(mode="after")
    def valid_rule_area_contours(self) -> PcbRuleAreaPolygonObservation:
        for label, ring in (
            ("outline", self.outline_nm),
            *(("hole", hole) for hole in self.holes_nm),
        ):
            if len(ring) < 3 or len(set(ring)) < 3 or ring[0] == ring[-1]:
                raise ValueError(
                    f"Native PCB rule-area {label} needs three distinct open-ring vertices"
                )
            area_twice = sum(
                first[0] * ring[(index + 1) % len(ring)][1]
                - ring[(index + 1) % len(ring)][0] * first[1]
                for index, first in enumerate(ring)
            )
            if area_twice == 0:
                raise ValueError(f"Native PCB rule-area {label} has zero area")
        return self


class PcbRuleAreaObservation(StrictModel):
    """Native KiCad keepout or placement rule area and its effective restrictions."""

    uuid: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    name: str
    layers: tuple[NonEmptyText, ...]
    net: NetName | None
    polygons: Annotated[tuple[PcbRuleAreaPolygonObservation, ...], Field(min_length=1)]
    forbids_tracks: bool
    forbids_vias: bool
    forbids_pads: bool
    forbids_zone_fills: bool
    forbids_footprints: bool

    @model_validator(mode="after")
    def unique_rule_area_layers(self) -> PcbRuleAreaObservation:
        if len({item.casefold() for item in self.layers}) != len(self.layers):
            raise ValueError("Native PCB rule-area layers must be unique")
        if len({(item.outline_nm, item.holes_nm) for item in self.polygons}) != len(self.polygons):
            raise ValueError("Native PCB rule-area polygons must be unique")
        return self


class PcbZoneObservation(PcbZoneIdentity):
    """Filled copper zone metadata and connected island count from KiCad."""

    name: str
    net: NetName | None
    filled_island_count: NonNegativeCount
    unanchored_pad_island_indexes: tuple[NonNegativeCount, ...] = ()
    filled_islands: tuple[PcbZoneFilledIslandObservation, ...] = ()

    @model_validator(mode="after")
    def unique_unanchored_islands(self) -> PcbZoneObservation:
        if len(set(self.unanchored_pad_island_indexes)) != len(self.unanchored_pad_island_indexes):
            raise ValueError("Native PCB unanchored-to-pad island indexes must be unique")
        island_indexes = {item.island_index for item in self.filled_islands}
        if len(island_indexes) != len(self.filled_islands):
            raise ValueError("Native PCB filled-island contours must have unique indexes")
        if any(index >= self.filled_island_count for index in island_indexes):
            raise ValueError("Native PCB filled-island contour index exceeds the island count")
        return self


class PcbZoneIslandIdentity(PcbZoneIdentity):
    """Exact filled-island index within one native zone and layer."""

    island_index: NonNegativeCount


class PcbViaObservation(StrictModel):
    """Stable native via geometry and layer transition in one connected component."""

    id: Digest
    net: NetName | None
    x_nm: int
    y_nm: int
    start_layer: NonEmptyText
    end_layer: NonEmptyText
    diameter_nm: PositiveCount
    drill_nm: PositiveCount
    kind: Literal["through", "blind", "buried", "micro"]
    multiplicity: PositiveCount

    @model_validator(mode="after")
    def distinct_layer_transition(self) -> PcbViaObservation:
        if self.start_layer.casefold() == self.end_layer.casefold():
            raise ValueError("Native via evidence must span at least two copper layers")
        return self


PcbTrackUuid = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
]


class PcbTrackObservation(StrictModel):
    """Native geometry and endpoint contacts for one KiCad copper track item."""

    uuid: PcbTrackUuid
    net: NetName | None
    layer: NonEmptyText
    width_nm: PositiveCount
    start_nm: tuple[int, int]
    end_nm: tuple[int, int]
    geometry_kind: Literal["segment", "arc"] | None = None
    start_pads: tuple[Reference, ...] = ()
    end_pads: tuple[Reference, ...] = ()
    start_vias: tuple[Digest, ...] = ()
    end_vias: tuple[Digest, ...] = ()
    start_tracks: tuple[PcbTrackUuid, ...] = ()
    end_tracks: tuple[PcbTrackUuid, ...] = ()

    @model_validator(mode="after")
    def unique_endpoint_contacts(self) -> PcbTrackObservation:
        for label, contacts in (
            ("start pads", self.start_pads),
            ("end pads", self.end_pads),
            ("start vias", self.start_vias),
            ("end vias", self.end_vias),
            ("start tracks", self.start_tracks),
            ("end tracks", self.end_tracks),
        ):
            if len({item.casefold() for item in contacts}) != len(contacts):
                raise ValueError(f"Native PCB track {label} must be unique")
        if any(
            item.casefold() == self.uuid.casefold()
            for item in (*self.start_tracks, *self.end_tracks)
        ):
            raise ValueError("Native PCB track endpoint contacts cannot refer to the track itself")
        return self


class PcbPadConnectivityObservation(StrictModel):
    """Native pad identity, copper-component members, and directly touched zone islands."""

    pad: Reference
    net: NetName | None
    footprint: NonEmptyText
    dnp: bool
    connected_pads: tuple[Reference, ...]
    connected_zones: tuple[PcbZoneIdentity, ...]
    connected_islands: tuple[PcbZoneIslandIdentity, ...]
    connected_vias: tuple[Digest, ...] = ()
    positions_nm: tuple[tuple[int, int], ...] = ()

    @model_validator(mode="after")
    def complete_pad_reference(self) -> PcbPadConnectivityObservation:
        if self.pad.count(".") != 1 or self.pad.casefold() not in {
            item.casefold() for item in self.connected_pads
        }:
            raise ValueError(
                "Native PCB pad evidence needs its exact reference and own connectivity"
            )
        if len({item.casefold() for item in self.connected_pads}) != len(self.connected_pads):
            raise ValueError("Native PCB connected pad references must be unique")
        if len(set(self.connected_vias)) != len(self.connected_vias):
            raise ValueError("Native PCB connected via identities must be unique")
        if len(set(self.positions_nm)) != len(self.positions_nm):
            raise ValueError("Native PCB physical pad centers must be unique")
        zone_keys = {(item.uuid.casefold(), item.layer.casefold()) for item in self.connected_zones}
        if len(zone_keys) != len(self.connected_zones):
            raise ValueError("Native PCB connected zone identities must be unique")
        island_keys = {
            (item.uuid.casefold(), item.layer.casefold(), item.island_index)
            for item in self.connected_islands
        }
        if len(island_keys) != len(self.connected_islands):
            raise ValueError("Native PCB connected island identities must be unique")
        return self


class PcbFootprintPlacementObservation(StrictModel):
    """Native placement transform and identity for one referenced PCB footprint."""

    reference: Reference
    footprint: NonEmptyText
    dnp: bool
    position_nm: tuple[int, int]
    orientation_microdegrees: Annotated[int, Field(ge=0, lt=360_000_000)]
    side: Literal["F.Cu", "B.Cu"]


class PcbAccessProbeObservation(StrictModel):
    """Target aperture and nearest different-net pad for one configured probe surface."""

    endpoint: Reference
    side: Literal["front", "back"]
    target_net: NetName | None
    target_exposed: bool
    obstacle: Reference | None
    obstacle_net: NetName | None
    distance_nm: NonNegativeCount | None
    target_aperture_shape: Literal["circle", "unsupported"] | None = None
    target_aperture_diameter_nm: NonNegativeCount | None = None

    @model_validator(mode="after")
    def complete_nearest_obstacle(self) -> PcbAccessProbeObservation:
        if self.obstacle is None:
            if self.obstacle_net is not None or self.distance_nm is not None:
                raise ValueError("Native probe obstacle fields must be present together")
            if not self.target_exposed and self.distance_nm is not None:
                raise ValueError("An unavailable target side cannot have an obstacle distance")
        elif self.distance_nm is None:
            raise ValueError("Native probe obstacle needs its measured distance")
        elif not self.target_exposed:
            raise ValueError("An unavailable target side cannot have an obstacle")
        elif self.obstacle.casefold() == self.endpoint.casefold():
            raise ValueError("Native probe obstacle cannot be the target endpoint")
        elif self.target_net is not None and self.obstacle_net == self.target_net:
            raise ValueError("Native probe obstacle must be on another net or unconnected")
        if self.target_aperture_shape == "circle":
            if self.target_aperture_diameter_nm is None or self.target_aperture_diameter_nm <= 0:
                raise ValueError("Circular native probe aperture needs a positive diameter")
        elif self.target_aperture_diameter_nm is not None:
            raise ValueError("Native probe aperture diameter requires a supported circular shape")
        if not self.target_exposed and self.target_aperture_shape is not None:
            raise ValueError("Unavailable target side cannot have aperture geometry")
        return self


class PcbNetTieObservation(StrictModel):
    """Native KiCad net-tie pad groups for one placed footprint."""

    reference: Identifier
    footprint: NonEmptyText
    dnp: bool
    pad_groups: tuple[tuple[Reference, ...], ...]

    @model_validator(mode="after")
    def scoped_unique_pad_groups(self) -> PcbNetTieObservation:
        pads = [pad for group in self.pad_groups for pad in group]
        if any(len(group) < 2 for group in self.pad_groups):
            raise ValueError("Native net-tie groups need at least two pads")
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in pads):
            raise ValueError("Native net-tie pad groups must belong to their footprint")
        if len({pad.casefold() for pad in pads}) != len(pads):
            raise ValueError("Native net-tie pads must occur in exactly one group")
        return self
