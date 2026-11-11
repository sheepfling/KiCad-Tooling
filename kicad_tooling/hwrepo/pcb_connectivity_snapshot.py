"""Versioned, source-bound PCB connectivity evidence snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonEmptyText, StrictModel
from .pcb_connectivity_edge_validation import validate_board_edge_evidence
from .pcb_connectivity_edges import PcbEdgeCutObservation
from .pcb_connectivity_hole_validation import validate_drill_hole_evidence
from .pcb_connectivity_holes import PcbDrillHoleObservation
from .pcb_connectivity_observations import (
    PcbAccessProbeObservation,
    PcbFootprintPlacementObservation,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbRuleAreaObservation,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneObservation,
)
from .pcb_connectivity_probe_validation import validate_access_probe_relationships
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceObservation


@dataclass(frozen=True, slots=True)
class _PcbZoneKey:
    """Case-insensitive identity for one native zone and copper layer."""

    uuid: str
    layer: str


@dataclass(frozen=True, slots=True)
class _PcbConnectivityIndex:
    """Read-only identity lookups shared by snapshot relationship checks."""

    pads_by_reference: Mapping[str, PcbPadConnectivityObservation]
    connected_pad_references: Mapping[str, frozenset[str]]
    vias_by_id: Mapping[str, PcbViaObservation]
    zones_by_identity: Mapping[_PcbZoneKey, PcbZoneObservation]
    tracks_by_uuid: Mapping[str, PcbTrackObservation]


def _zone_key(uuid: str, layer: str) -> _PcbZoneKey:
    return _PcbZoneKey(uuid=uuid.casefold(), layer=layer.casefold())


class PcbConnectivitySnapshot(StrictModel):
    """Retained, deterministic native connectivity evidence for an exact board."""

    schema_version: Literal[
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
    ] = "3"
    board_sha256: Digest
    kicad_version: NonEmptyText
    image: NonEmptyText
    probe_sha256: Digest
    zones_refilled: bool
    pads: tuple[PcbPadConnectivityObservation, ...]
    net_ties: tuple[PcbNetTieObservation, ...]
    zones: tuple[PcbZoneObservation, ...]
    vias: tuple[PcbViaObservation, ...] = ()
    access_probe_observations: tuple[PcbAccessProbeObservation, ...] = ()
    access_probe_requests_sha256: Digest | None = None
    tracks: tuple[PcbTrackObservation, ...] = ()
    copper_layers: tuple[NonEmptyText, ...] = ()
    rule_areas: tuple[PcbRuleAreaObservation, ...] = ()
    footprints: tuple[PcbFootprintPlacementObservation, ...] = ()
    edge_cuts: tuple[PcbEdgeCutObservation, ...] = ()
    drill_holes: tuple[PcbDrillHoleObservation, ...] = ()
    touch_pad_clearance_observations: tuple[PcbTouchPadClearanceObservation, ...] = ()
    touch_pad_clearance_requests_sha256: Digest | None = None

    @model_validator(mode="after")
    def validate_snapshot_contract(self) -> PcbConnectivitySnapshot:
        schema_version = int(self.schema_version)
        _validate_initial_identity_uniqueness(self)
        _validate_touch_pad_request_contract(self, schema_version)
        _validate_v3_inventory_contract(self, schema_version)
        _validate_zone_identity_uniqueness(self)
        index = _build_connectivity_index(self)
        _validate_pad_relationships(self, index)
        _validate_via_relationships(self, index)
        _validate_zone_relationships(self, index, schema_version)
        _validate_snapshot_inventory_contract(self, schema_version)
        _validate_track_relationships(self, index, schema_version)
        _validate_filled_zone_contours(self, schema_version)
        validate_access_probe_relationships(
            self.access_probe_observations,
            index.pads_by_reference,
            index.vias_by_id,
            index.tracks_by_uuid,
            self.zones,
            self.footprints,
            schema_version,
        )
        validate_board_edge_evidence(
            self.edge_cuts,
            self.access_probe_observations,
            schema_version=schema_version,
            edge_inventory_present="edge_cuts" in self.model_fields_set,
        )
        validate_drill_hole_evidence(
            self.drill_holes,
            self.access_probe_observations,
            index.pads_by_reference,
            index.vias_by_id,
            self.footprints,
            schema_version=schema_version,
            inventory_present="drill_holes" in self.model_fields_set,
        )
        _validate_rule_area_contract(self, schema_version)
        _validate_footprint_contract(self, schema_version)
        _validate_touch_pad_observations(self, index, schema_version)
        _validate_net_tie_members(self, index)
        return self


def _validate_initial_identity_uniqueness(snapshot: PcbConnectivitySnapshot) -> None:
    if len({item.pad.casefold() for item in snapshot.pads}) != len(snapshot.pads):
        raise ValueError("Native PCB evidence contains duplicate pad references")
    if len({item.reference.casefold() for item in snapshot.net_ties}) != len(snapshot.net_ties):
        raise ValueError("Native PCB evidence contains duplicate net-tie references")
    via_ids = [item.id for item in snapshot.vias]
    if len(set(via_ids)) != len(via_ids):
        raise ValueError("Native PCB evidence contains duplicate via identities")
    track_ids = [item.uuid.casefold() for item in snapshot.tracks]
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("Native PCB evidence contains duplicate track identities")
    touch_requirement_ids = [
        item.requirement_id.casefold() for item in snapshot.touch_pad_clearance_observations
    ]
    if len(set(touch_requirement_ids)) != len(touch_requirement_ids):
        raise ValueError("Native PCB evidence contains duplicate touch-pad requirements")


def _validate_touch_pad_request_contract(
    snapshot: PcbConnectivitySnapshot, schema_version: int
) -> None:
    if schema_version >= 14:
        if (
            "touch_pad_clearance_observations" not in snapshot.model_fields_set
            or "touch_pad_clearance_requests_sha256" not in snapshot.model_fields_set
        ):
            raise ValueError("Native PCB schema v14+ requires explicit touch-pad probe evidence")
        if (snapshot.touch_pad_clearance_requests_sha256 is None) != (
            not snapshot.touch_pad_clearance_observations
        ):
            raise ValueError("Native touch-pad request hash and observations must be paired")
    elif (
        snapshot.touch_pad_clearance_requests_sha256 is not None
        or snapshot.touch_pad_clearance_observations
    ):
        raise ValueError("Touch-pad probe evidence requires native PCB schema v14+")


def _validate_v3_inventory_contract(snapshot: PcbConnectivitySnapshot, schema_version: int) -> None:
    if schema_version < 3:
        return
    if "vias" not in snapshot.model_fields_set:
        raise ValueError("Native PCB schema v3 requires an explicit via inventory")
    if any("connected_vias" not in item.model_fields_set for item in snapshot.pads):
        raise ValueError("Native PCB schema v3 requires explicit per-pad via evidence")
    if any("unanchored_pad_island_indexes" not in item.model_fields_set for item in snapshot.zones):
        raise ValueError("Native PCB schema v3 requires explicit zone island-anchor evidence")


def _validate_zone_identity_uniqueness(snapshot: PcbConnectivitySnapshot) -> None:
    zone_keys = {_zone_key(item.uuid, item.layer) for item in snapshot.zones}
    if len(zone_keys) != len(snapshot.zones):
        raise ValueError("Native PCB evidence contains duplicate zone identities")


def _build_connectivity_index(snapshot: PcbConnectivitySnapshot) -> _PcbConnectivityIndex:
    return _PcbConnectivityIndex(
        pads_by_reference=MappingProxyType({item.pad.casefold(): item for item in snapshot.pads}),
        connected_pad_references=MappingProxyType(
            {
                item.pad.casefold(): frozenset(
                    reference.casefold() for reference in item.connected_pads
                )
                for item in snapshot.pads
            }
        ),
        vias_by_id=MappingProxyType({item.id: item for item in snapshot.vias}),
        zones_by_identity=MappingProxyType(
            {_zone_key(item.uuid, item.layer): item for item in snapshot.zones}
        ),
        tracks_by_uuid=MappingProxyType({item.uuid.casefold(): item for item in snapshot.tracks}),
    )


def _validate_pad_relationships(
    snapshot: PcbConnectivitySnapshot, index: _PcbConnectivityIndex
) -> None:
    if any(
        not {reference.casefold() for reference in item.connected_pads}
        <= index.pads_by_reference.keys()
        for item in snapshot.pads
    ):
        raise ValueError("Native PCB connectivity refers to a pad absent from the board")
    for pad in snapshot.pads:
        for reference in pad.connected_pads:
            connected_pad = index.pads_by_reference[reference.casefold()]
            if connected_pad.net != pad.net:
                raise ValueError("Native PCB connected pads have different nets")
            if (
                pad.pad.casefold()
                not in index.connected_pad_references[connected_pad.pad.casefold()]
            ):
                raise ValueError("Native PCB connected pad membership must be symmetric")


def _validate_via_relationships(
    snapshot: PcbConnectivitySnapshot, index: _PcbConnectivityIndex
) -> None:
    for pad in snapshot.pads:
        if not set(pad.connected_vias) <= index.vias_by_id.keys():
            raise ValueError("Native PCB connectivity refers to a via absent from the board")
        for via_id in pad.connected_vias:
            via = index.vias_by_id[via_id]
            if via.net != pad.net:
                raise ValueError("Native PCB pad and connected via have different nets")


def _validate_zone_relationships(
    snapshot: PcbConnectivitySnapshot,
    index: _PcbConnectivityIndex,
    schema_version: int,
) -> None:
    mapped_islands_by_zone: dict[_PcbZoneKey, set[int]] = {}
    for pad in snapshot.pads:
        connected_zone_keys = {
            _zone_key(identity.uuid, identity.layer) for identity in pad.connected_zones
        }
        mapped_zone_keys: set[_PcbZoneKey] = set()
        for identity in pad.connected_zones:
            key = _zone_key(identity.uuid, identity.layer)
            zone = index.zones_by_identity.get(key)
            if zone is None:
                raise ValueError("Native PCB pad refers to a zone absent from the board")
            if zone.net != pad.net:
                raise ValueError("Native PCB pad and connected zone have different nets")
        for island in pad.connected_islands:
            key = _zone_key(island.uuid, island.layer)
            zone = index.zones_by_identity.get(key)
            if zone is None:
                raise ValueError(
                    "Native PCB pad refers to an island in a zone absent from the board"
                )
            if key not in connected_zone_keys:
                raise ValueError("Native PCB pad island is not in its connected zone evidence")
            if island.island_index >= zone.filled_island_count:
                raise ValueError("Native PCB pad island index exceeds the filled zone island count")
            mapped_zone_keys.add(key)
            mapped_islands_by_zone.setdefault(key, set()).add(island.island_index)
        if mapped_zone_keys != connected_zone_keys:
            raise ValueError("Native PCB connected zones need exact filled-island evidence")
    if schema_version >= 3:
        for key, zone in index.zones_by_identity.items():
            expected_unanchored = set(range(zone.filled_island_count)) - (
                mapped_islands_by_zone.get(key, set())
            )
            if set(zone.unanchored_pad_island_indexes) != expected_unanchored:
                raise ValueError(
                    "Native PCB zone unanchored-to-pad island indexes do not match "
                    "the pad-to-island evidence"
                )


def _validate_snapshot_inventory_contract(
    snapshot: PcbConnectivitySnapshot, schema_version: int
) -> None:
    if schema_version >= 4:
        if "access_probe_observations" not in snapshot.model_fields_set:
            raise ValueError("Native PCB schema v4+ requires explicit probe observations")
        if "access_probe_requests_sha256" not in snapshot.model_fields_set:
            raise ValueError("Native PCB schema v4+ requires explicit probe request evidence")
        if bool(snapshot.access_probe_observations) != (
            snapshot.access_probe_requests_sha256 is not None
        ):
            raise ValueError("Native PCB probe observations need matching request evidence")
    if schema_version >= 5 and any(
        "positions_nm" not in item.model_fields_set or not item.positions_nm
        for item in snapshot.pads
    ):
        raise ValueError("Native PCB schema v5+ requires physical pad-center positions")
    if schema_version >= 6 and "tracks" not in snapshot.model_fields_set:
        raise ValueError(
            f"Native PCB schema v{snapshot.schema_version} requires an explicit track inventory"
        )
    if schema_version >= 7:
        if "copper_layers" not in snapshot.model_fields_set or len(snapshot.copper_layers) < 2:
            raise ValueError(
                f"Native PCB schema v{snapshot.schema_version} requires the actual copper stack inventory"
            )
        if len({item.casefold() for item in snapshot.copper_layers}) != len(snapshot.copper_layers):
            raise ValueError("Native PCB copper stack contains duplicate layer names")


def _validate_track_relationships(
    snapshot: PcbConnectivitySnapshot,
    index: _PcbConnectivityIndex,
    schema_version: int,
) -> None:
    if schema_version < 8:
        return
    for track in snapshot.tracks:
        if any(
            field not in track.model_fields_set
            for field in (
                "geometry_kind",
                "start_pads",
                "end_pads",
                "start_vias",
                "end_vias",
                "start_tracks",
                "end_tracks",
            )
        ):
            raise ValueError(
                f"Native PCB schema v{snapshot.schema_version} requires explicit track geometry and endpoint contacts"
            )
        if track.geometry_kind is None:
            raise ValueError(
                f"Native PCB schema v{snapshot.schema_version} track geometry kind cannot be unavailable"
            )
        if schema_version >= 15:
            _validate_track_arc_fields(track)
        if any(
            pad.casefold() not in index.pads_by_reference
            for pad in (*track.start_pads, *track.end_pads)
        ):
            raise ValueError("Native PCB track endpoint refers to an absent pad")
        if any(
            index.pads_by_reference[pad.casefold()].net != track.net
            for pad in (*track.start_pads, *track.end_pads)
        ):
            raise ValueError("Native PCB track endpoint pad has a different net")
        if any(via not in index.vias_by_id for via in (*track.start_vias, *track.end_vias)):
            raise ValueError("Native PCB track endpoint refers to an absent via")
        if any(
            index.vias_by_id[via].net != track.net for via in (*track.start_vias, *track.end_vias)
        ):
            raise ValueError("Native PCB track endpoint via has a different net")
        if any(
            contact.casefold() not in index.tracks_by_uuid
            for contact in (*track.start_tracks, *track.end_tracks)
        ):
            raise ValueError("Native PCB track endpoint refers to an absent track")
        if any(
            index.tracks_by_uuid[contact.casefold()].net != track.net
            for contact in (*track.start_tracks, *track.end_tracks)
        ):
            raise ValueError("Native PCB track endpoint contact has a different net")


def _validate_track_arc_fields(track: PcbTrackObservation) -> None:
    if "arc_mid_nm" not in track.model_fields_set or "arc_length_nm" not in track.model_fields_set:
        raise ValueError("Native PCB schema v15+ requires explicit arc geometry fields")
    if track.geometry_kind == "arc" and (track.arc_mid_nm is None or track.arc_length_nm is None):
        raise ValueError("Native PCB schema v15+ arcs require midpoint and length evidence")
    if track.geometry_kind == "segment" and (
        track.arc_mid_nm is not None or track.arc_length_nm is not None
    ):
        raise ValueError("Native PCB schema v15+ segments cannot carry arc evidence")


def _validate_filled_zone_contours(snapshot: PcbConnectivitySnapshot, schema_version: int) -> None:
    if schema_version < 9:
        return
    for zone in snapshot.zones:
        if "filled_islands" not in zone.model_fields_set:
            raise ValueError(
                "Native PCB schema v9 requires explicit filled-island contour geometry"
            )
        indexes = {item.island_index for item in zone.filled_islands}
        if indexes != set(range(zone.filled_island_count)):
            raise ValueError("Native PCB schema v9 needs one contour for every filled zone island")


def _validate_rule_area_contract(snapshot: PcbConnectivitySnapshot, schema_version: int) -> None:
    if schema_version < 11:
        return
    if "rule_areas" not in snapshot.model_fields_set:
        raise ValueError(
            f"Native PCB schema v{snapshot.schema_version} requires explicit rule-area evidence"
        )
    rule_area_ids = [item.uuid.casefold() for item in snapshot.rule_areas]
    if len(set(rule_area_ids)) != len(rule_area_ids):
        raise ValueError("Native PCB evidence contains duplicate rule-area identities")
    copper_layers = {layer.casefold() for layer in snapshot.copper_layers}
    for area in snapshot.rule_areas:
        if "name" not in area.model_fields_set:
            raise ValueError("Native PCB schema v11 requires explicit rule-area names")
        if any(layer.casefold() not in copper_layers for layer in area.layers):
            raise ValueError("Native PCB rule-area layers are outside the copper stack")


def _validate_footprint_contract(
    snapshot: PcbConnectivitySnapshot,
    schema_version: int,
) -> None:
    if schema_version < 12:
        return
    if "footprints" not in snapshot.model_fields_set:
        raise ValueError(
            f"Native PCB schema v{snapshot.schema_version} requires explicit footprint placement evidence"
        )
    footprint_rows = {item.reference.casefold(): item for item in snapshot.footprints}
    if len(footprint_rows) != len(snapshot.footprints):
        raise ValueError("Native PCB evidence contains duplicate footprint references")
    if any(item.side not in snapshot.copper_layers for item in snapshot.footprints):
        raise ValueError("Native PCB footprint side is outside the copper stack")
    if schema_version >= 13 and any(
        "value" not in item.model_fields_set or item.value is None for item in snapshot.footprints
    ):
        raise ValueError("Native PCB schema v13 requires explicit footprint value fields")
    for pad in snapshot.pads:
        reference = pad.pad.rsplit(".", 1)[0].casefold()
        footprint = footprint_rows.get(reference)
        if footprint is None:
            raise ValueError("Native PCB pad refers to an unobserved footprint placement")
        if footprint.footprint != pad.footprint or footprint.dnp != pad.dnp:
            raise ValueError("Native PCB pad identity differs from its footprint placement")


def _validate_touch_pad_observations(
    snapshot: PcbConnectivitySnapshot,
    index: _PcbConnectivityIndex,
    schema_version: int,
) -> None:
    if schema_version < 14:
        return
    for observation in snapshot.touch_pad_clearance_observations:
        if observation.status != "MEASURED":
            continue
        pad = index.pads_by_reference.get(observation.pad.casefold())
        if pad is None or pad.net != observation.observed_pad_net:
            raise ValueError("Measured touch-pad observation disagrees with native pad data")
        if observation.closest_zone_uuid is None:
            raise ValueError("Measured touch-pad observation has no reference zone UUID")
        zone = index.zones_by_identity.get(
            _zone_key(observation.closest_zone_uuid, observation.layer)
        )
        if zone is None or zone.net != observation.reference_net or zone.filled_island_count == 0:
            raise ValueError("Measured touch-pad observation disagrees with native zone data")


def _validate_net_tie_members(
    snapshot: PcbConnectivitySnapshot, index: _PcbConnectivityIndex
) -> None:
    for tie in snapshot.net_ties:
        for member in (pad for group in tie.pad_groups for pad in group):
            observed = index.pads_by_reference.get(member.casefold())
            if observed is None or observed.footprint != tie.footprint or observed.dnp != tie.dnp:
                raise ValueError("Native net-tie group differs from its observed footprint pads")
