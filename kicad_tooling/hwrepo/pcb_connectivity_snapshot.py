"""Versioned, source-bound PCB connectivity evidence snapshots."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, NonEmptyText, StrictModel
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
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceObservation


class PcbConnectivitySnapshot(StrictModel):
    """Retained, deterministic native connectivity evidence for an exact board."""

    schema_version: Literal[
        "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"
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
    touch_pad_clearance_observations: tuple[PcbTouchPadClearanceObservation, ...] = ()
    touch_pad_clearance_requests_sha256: Digest | None = None

    @model_validator(mode="after")
    def unique_observed_items(self) -> PcbConnectivitySnapshot:
        if len({item.pad.casefold() for item in self.pads}) != len(self.pads):
            raise ValueError("Native PCB evidence contains duplicate pad references")
        if len({item.reference.casefold() for item in self.net_ties}) != len(self.net_ties):
            raise ValueError("Native PCB evidence contains duplicate net-tie references")
        via_ids = [item.id for item in self.vias]
        if len(set(via_ids)) != len(via_ids):
            raise ValueError("Native PCB evidence contains duplicate via identities")
        track_ids = [item.uuid.casefold() for item in self.tracks]
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("Native PCB evidence contains duplicate track identities")
        touch_requirement_ids = [
            item.requirement_id.casefold() for item in self.touch_pad_clearance_observations
        ]
        if len(set(touch_requirement_ids)) != len(touch_requirement_ids):
            raise ValueError("Native PCB evidence contains duplicate touch-pad requirements")
        if self.schema_version in {"14", "15"}:
            if (
                "touch_pad_clearance_observations" not in self.model_fields_set
                or "touch_pad_clearance_requests_sha256" not in self.model_fields_set
            ):
                raise ValueError(
                    "Native PCB schema v14+ requires explicit touch-pad probe evidence"
                )
            if (self.touch_pad_clearance_requests_sha256 is None) != (
                not self.touch_pad_clearance_observations
            ):
                raise ValueError("Native touch-pad request hash and observations must be paired")
        elif (
            self.touch_pad_clearance_requests_sha256 is not None
            or self.touch_pad_clearance_observations
        ):
            raise ValueError("Touch-pad probe evidence requires native PCB schema v14+")
        if self.schema_version in {
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
        }:
            if "vias" not in self.model_fields_set:
                raise ValueError("Native PCB schema v3 requires an explicit via inventory")
            if any("connected_vias" not in item.model_fields_set for item in self.pads):
                raise ValueError("Native PCB schema v3 requires explicit per-pad via evidence")
            if any(
                "unanchored_pad_island_indexes" not in item.model_fields_set for item in self.zones
            ):
                raise ValueError(
                    "Native PCB schema v3 requires explicit zone island-anchor evidence"
                )
        zone_keys = {(item.uuid.casefold(), item.layer.casefold()) for item in self.zones}
        if len(zone_keys) != len(self.zones):
            raise ValueError("Native PCB evidence contains duplicate zone identities")
        pads_by_name = {item.pad.casefold(): item for item in self.pads}
        connected_pad_names = {
            item.pad.casefold(): {reference.casefold() for reference in item.connected_pads}
            for item in self.pads
        }
        known_pad_names = set(pads_by_name)
        if any(
            not {reference.casefold() for reference in item.connected_pads} <= known_pad_names
            for item in self.pads
        ):
            raise ValueError("Native PCB connectivity refers to a pad absent from the board")
        for pad in self.pads:
            for reference in pad.connected_pads:
                connected_pad = pads_by_name[reference.casefold()]
                if connected_pad.net != pad.net:
                    raise ValueError("Native PCB connected pads have different nets")
                if pad.pad.casefold() not in connected_pad_names[connected_pad.pad.casefold()]:
                    raise ValueError("Native PCB connected pad membership must be symmetric")
        vias_by_id = {item.id: item for item in self.vias}
        for pad in self.pads:
            if not set(pad.connected_vias) <= vias_by_id.keys():
                raise ValueError("Native PCB connectivity refers to a via absent from the board")
            for via_id in pad.connected_vias:
                via = vias_by_id[via_id]
                if via.net != pad.net:
                    raise ValueError("Native PCB pad and connected via have different nets")
        zones_by_key = {(item.uuid.casefold(), item.layer.casefold()): item for item in self.zones}
        mapped_islands_by_zone: dict[tuple[str, str], set[int]] = {}
        for pad in self.pads:
            connected_zone_keys = {
                (identity.uuid.casefold(), identity.layer.casefold())
                for identity in pad.connected_zones
            }
            mapped_zone_keys: set[tuple[str, str]] = set()
            for identity in pad.connected_zones:
                zone = zones_by_key.get((identity.uuid.casefold(), identity.layer.casefold()))
                if zone is None:
                    raise ValueError("Native PCB pad refers to a zone absent from the board")
                if zone.net != pad.net:
                    raise ValueError("Native PCB pad and connected zone have different nets")
            for island in pad.connected_islands:
                key = (island.uuid.casefold(), island.layer.casefold())
                zone = zones_by_key.get(key)
                if zone is None:
                    raise ValueError(
                        "Native PCB pad refers to an island in a zone absent from the board"
                    )
                if key not in connected_zone_keys:
                    raise ValueError("Native PCB pad island is not in its connected zone evidence")
                if island.island_index >= zone.filled_island_count:
                    raise ValueError(
                        "Native PCB pad island index exceeds the filled zone island count"
                    )
                mapped_zone_keys.add(key)
                mapped_islands_by_zone.setdefault(key, set()).add(island.island_index)
            if mapped_zone_keys != connected_zone_keys:
                raise ValueError("Native PCB connected zones need exact filled-island evidence")
        if self.schema_version in {
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
        }:
            for key, zone in zones_by_key.items():
                expected_unanchored = set(range(zone.filled_island_count)) - (
                    mapped_islands_by_zone.get(key, set())
                )
                if set(zone.unanchored_pad_island_indexes) != expected_unanchored:
                    raise ValueError(
                        "Native PCB zone unanchored-to-pad island indexes do not match "
                        "the pad-to-island evidence"
                    )
        if self.schema_version in {
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
        }:
            if "access_probe_observations" not in self.model_fields_set:
                raise ValueError("Native PCB schema v4+ requires explicit probe observations")
            if "access_probe_requests_sha256" not in self.model_fields_set:
                raise ValueError("Native PCB schema v4+ requires explicit probe request evidence")
            if bool(self.access_probe_observations) != (
                self.access_probe_requests_sha256 is not None
            ):
                raise ValueError("Native PCB probe observations need matching request evidence")
        if self.schema_version in {
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
        } and any(
            "positions_nm" not in item.model_fields_set or not item.positions_nm
            for item in self.pads
        ):
            raise ValueError("Native PCB schema v5+ requires physical pad-center positions")
        if (
            self.schema_version in {"6", "7", "8", "9", "10", "11", "12", "13", "14", "15"}
            and "tracks" not in self.model_fields_set
        ):
            raise ValueError(
                f"Native PCB schema v{self.schema_version} requires an explicit track inventory"
            )
        if self.schema_version in {"7", "8", "9", "10", "11", "12", "13", "14", "15"}:
            if "copper_layers" not in self.model_fields_set or len(self.copper_layers) < 2:
                raise ValueError(
                    f"Native PCB schema v{self.schema_version} requires the actual copper stack inventory"
                )
            if len({item.casefold() for item in self.copper_layers}) != len(self.copper_layers):
                raise ValueError("Native PCB copper stack contains duplicate layer names")
        if self.schema_version in {"8", "9", "10", "11", "12", "13", "14", "15"}:
            tracks_by_uuid = {item.uuid.casefold(): item for item in self.tracks}
            for track in self.tracks:
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
                        f"Native PCB schema v{self.schema_version} requires explicit track geometry and endpoint contacts"
                    )
                if track.geometry_kind is None:
                    raise ValueError(
                        f"Native PCB schema v{self.schema_version} track geometry kind cannot be unavailable"
                    )
                if self.schema_version == "15":
                    if (
                        "arc_mid_nm" not in track.model_fields_set
                        or "arc_length_nm" not in track.model_fields_set
                    ):
                        raise ValueError(
                            "Native PCB schema v15 requires explicit arc geometry fields"
                        )
                    if track.geometry_kind == "arc" and (
                        track.arc_mid_nm is None or track.arc_length_nm is None
                    ):
                        raise ValueError(
                            "Native PCB schema v15 arcs require midpoint and length evidence"
                        )
                    if track.geometry_kind == "segment" and (
                        track.arc_mid_nm is not None or track.arc_length_nm is not None
                    ):
                        raise ValueError("Native PCB schema v15 segments cannot carry arc evidence")
                if any(
                    pad.casefold() not in pads_by_name
                    for pad in (*track.start_pads, *track.end_pads)
                ):
                    raise ValueError("Native PCB track endpoint refers to an absent pad")
                if any(
                    pads_by_name[pad.casefold()].net != track.net
                    for pad in (*track.start_pads, *track.end_pads)
                ):
                    raise ValueError("Native PCB track endpoint pad has a different net")
                if any(via not in vias_by_id for via in (*track.start_vias, *track.end_vias)):
                    raise ValueError("Native PCB track endpoint refers to an absent via")
                if any(
                    vias_by_id[via].net != track.net for via in (*track.start_vias, *track.end_vias)
                ):
                    raise ValueError("Native PCB track endpoint via has a different net")
                if any(
                    contact.casefold() not in tracks_by_uuid
                    for contact in (*track.start_tracks, *track.end_tracks)
                ):
                    raise ValueError("Native PCB track endpoint refers to an absent track")
                if any(
                    tracks_by_uuid[contact.casefold()].net != track.net
                    for contact in (*track.start_tracks, *track.end_tracks)
                ):
                    raise ValueError("Native PCB track endpoint contact has a different net")
        if self.schema_version in {"9", "10", "11", "12", "13", "14", "15"}:
            for zone in self.zones:
                if "filled_islands" not in zone.model_fields_set:
                    raise ValueError(
                        "Native PCB schema v9 requires explicit filled-island contour geometry"
                    )
                indexes = {item.island_index for item in zone.filled_islands}
                if indexes != set(range(zone.filled_island_count)):
                    raise ValueError(
                        "Native PCB schema v9 needs one contour for every filled zone island"
                    )
        probe_keys = [
            (item.endpoint.casefold(), item.side.casefold())
            for item in self.access_probe_observations
        ]
        if len(set(probe_keys)) != len(probe_keys):
            raise ValueError("Native PCB probe endpoint and side identities must be unique")
        for item in self.access_probe_observations:
            target = pads_by_name.get(item.endpoint.casefold())
            if target is None:
                raise ValueError("Native PCB probe observation refers to an unobserved pad")
            if target.net != item.target_net:
                raise ValueError("Native PCB probe target net differs from its pad inventory")
            if item.obstacle is not None:
                obstacle = pads_by_name.get(item.obstacle.casefold())
                if obstacle is None:
                    raise ValueError(
                        "Native PCB probe observation refers to an unobserved obstacle pad"
                    )
                if obstacle.net != item.obstacle_net:
                    raise ValueError("Native PCB probe obstacle net differs from its pad inventory")
            if self.schema_version in {"10", "11", "12", "13", "14", "15"} and any(
                field not in item.model_fields_set
                for field in ("target_aperture_shape", "target_aperture_diameter_nm")
            ):
                raise ValueError(
                    "Native PCB schema v10+ requires explicit target aperture evidence"
                )
        if self.schema_version in {"11", "12", "13", "14", "15"}:
            if "rule_areas" not in self.model_fields_set:
                raise ValueError(
                    f"Native PCB schema v{self.schema_version} requires explicit rule-area evidence"
                )
            rule_area_ids = [item.uuid.casefold() for item in self.rule_areas]
            if len(set(rule_area_ids)) != len(rule_area_ids):
                raise ValueError("Native PCB evidence contains duplicate rule-area identities")
            for area in self.rule_areas:
                if "name" not in area.model_fields_set:
                    raise ValueError("Native PCB schema v11 requires explicit rule-area names")
                copper_layers = {layer.casefold() for layer in self.copper_layers}
                if any(layer.casefold() not in copper_layers for layer in area.layers):
                    raise ValueError("Native PCB rule-area layers are outside the copper stack")
        if self.schema_version in {"12", "13", "14", "15"}:
            if "footprints" not in self.model_fields_set:
                raise ValueError(
                    f"Native PCB schema v{self.schema_version} requires explicit footprint placement evidence"
                )
            footprint_rows = {item.reference.casefold(): item for item in self.footprints}
            if len(footprint_rows) != len(self.footprints):
                raise ValueError("Native PCB evidence contains duplicate footprint references")
            if any(item.side not in self.copper_layers for item in self.footprints):
                raise ValueError("Native PCB footprint side is outside the copper stack")
            if self.schema_version in {"13", "14", "15"} and any(
                "value" not in item.model_fields_set or item.value is None
                for item in self.footprints
            ):
                raise ValueError("Native PCB schema v13 requires explicit footprint value fields")
            for pad in self.pads:
                reference = pad.pad.rsplit(".", 1)[0].casefold()
                footprint = footprint_rows.get(reference)
                if footprint is None:
                    raise ValueError("Native PCB pad refers to an unobserved footprint placement")
                if footprint.footprint != pad.footprint or footprint.dnp != pad.dnp:
                    raise ValueError("Native PCB pad identity differs from its footprint placement")
        if self.schema_version in {"14", "15"}:
            for observation in self.touch_pad_clearance_observations:
                if observation.status != "MEASURED":
                    continue
                pad = pads_by_name.get(observation.pad.casefold())
                if pad is None or pad.net != observation.observed_pad_net:
                    raise ValueError(
                        "Measured touch-pad observation disagrees with native pad data"
                    )
                if observation.closest_zone_uuid is None:
                    raise ValueError("Measured touch-pad observation has no reference zone UUID")
                zone = zones_by_key.get(
                    (observation.closest_zone_uuid.casefold(), observation.layer.casefold())
                )
                if (
                    zone is None
                    or zone.net != observation.reference_net
                    or zone.filled_island_count == 0
                ):
                    raise ValueError(
                        "Measured touch-pad observation disagrees with native zone data"
                    )
        for tie in self.net_ties:
            for member in (pad for group in tie.pad_groups for pad in group):
                observed = pads_by_name.get(member.casefold())
                if (
                    observed is None
                    or observed.footprint != tie.footprint
                    or observed.dnp != tie.dnp
                ):
                    raise ValueError(
                        "Native net-tie group differs from its observed footprint pads"
                    )
        return self
