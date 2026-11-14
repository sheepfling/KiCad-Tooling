"""Validate retained PCB drill-hole inventories and probe relationships."""

from __future__ import annotations

from collections.abc import Mapping

from .pcb_connectivity_holes import PcbDrillHoleObservation
from .pcb_connectivity_observations import (
    PcbAccessProbeObservation,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbViaObservation,
)

_HOLE_FIELDS = ("hole_obstacle_id", "hole_obstacle_distance_nm")


def validate_drill_hole_evidence(
    holes: tuple[PcbDrillHoleObservation, ...],
    observations: tuple[PcbAccessProbeObservation, ...],
    pads_by_reference: Mapping[str, PcbPadConnectivityObservation],
    vias_by_id: Mapping[str, PcbViaObservation],
    footprints: tuple[PcbFootprintPlacementObservation, ...],
    *,
    schema_version: int,
    inventory_present: bool,
) -> None:
    """Require source identities for every measured outer-surface drill opening."""
    if schema_version < 22 or (schema_version == 23 and not inventory_present):
        if holes or any(
            getattr(item, field) is not None for item in observations for field in _HOLE_FIELDS
        ):
            raise ValueError("Drill-hole evidence requires native PCB schema v22+")
        return
    if not inventory_present:
        raise ValueError("Native PCB schema v22+ requires explicit drill-hole inventory")

    holes_by_id = {item.id.casefold(): item for item in holes}
    if len(holes_by_id) != len(holes):
        raise ValueError("Native PCB drill-hole identities must be unique")
    footprints_by_reference = {item.reference.casefold(): item for item in footprints}
    for hole in holes:
        if hole.kind == "pad":
            assert hole.pad_uuid is not None
            assert hole.footprint_reference is not None and hole.footprint is not None
            footprint = footprints_by_reference.get(hole.footprint_reference.casefold())
            if footprint is None or footprint.dnp or footprint.footprint != hole.footprint:
                raise ValueError("Native drill hole refers to an absent or unfitted footprint")
            if hole.pad is not None:
                pad = pads_by_reference.get(hole.pad.casefold())
                if pad is None or pad.dnp or pad.footprint != hole.footprint:
                    raise ValueError("Native drill hole refers to an absent or unfitted pad")
                if hole.position_nm not in pad.positions_nm:
                    raise ValueError("Native drill-hole center differs from its pad inventory")
        else:
            assert hole.via_id is not None
            via = vias_by_id.get(hole.via_id)
            if via is None:
                raise ValueError("Native drill hole refers to an absent via")
            if hole.position_nm != (via.x_nm, via.y_nm):
                raise ValueError("Native drill-hole center differs from its via inventory")
            if hole.drill_size_nm != (via.drill_nm, via.drill_nm):
                raise ValueError("Native drill-hole size differs from its via inventory")

    for observation in observations:
        if any(field not in observation.model_fields_set for field in _HOLE_FIELDS):
            raise ValueError("Native PCB schema v22+ requires explicit probe drill-hole evidence")
        hole = (
            None
            if observation.hole_obstacle_id is None
            else holes_by_id.get(observation.hole_obstacle_id.casefold())
        )
        if observation.hole_obstacle_id is not None and hole is None:
            raise ValueError("Native PCB probe refers to an unobserved drill hole")
        if hole is not None:
            if observation.side not in hole.surfaces:
                raise ValueError("Native PCB probe drill hole is not open on the requested surface")
            if hole.pad is not None and hole.pad.casefold() == observation.endpoint.casefold():
                raise ValueError("Native PCB probe cannot use the target pad as a drill obstacle")
        if observation.target_exposed:
            eligible = any(
                observation.side in item.surfaces
                and (item.pad is None or item.pad.casefold() != observation.endpoint.casefold())
                for item in holes
            )
            if eligible != (hole is not None):
                raise ValueError("Native PCB probe drill-hole evidence omits surface inventory")
