"""Validate the native board-thickness and outer-copper surface evidence."""

from __future__ import annotations

from collections.abc import Sequence

from .pcb_connectivity_observations import (
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
)


def validate_outer_copper_surface_evidence(
    *,
    pads: Sequence[PcbPadConnectivityObservation],
    footprints: Sequence[PcbFootprintPlacementObservation],
    copper_layers: Sequence[str],
    board_thickness_nm: int | None,
    schema_version: int,
) -> None:
    """Require source-complete outer-surface centers for native snapshot schema v23."""
    surface_field = "outer_copper_centers"
    if schema_version < 23:
        if board_thickness_nm is not None or any(pad.outer_copper_centers for pad in pads):
            raise ValueError("Outer-copper surface evidence requires native PCB schema v23+")
        return
    if board_thickness_nm is None:
        raise ValueError("Native PCB schema v23+ requires board-thickness evidence")
    if board_thickness_nm <= 0:
        raise ValueError("Native PCB board thickness must be positive")
    available_layers = {layer.casefold() for layer in copper_layers}
    if not {"f.cu", "b.cu"} <= available_layers:
        raise ValueError("Native PCB schema v23+ requires both outer copper layers")
    footprint_sides = {item.reference.casefold(): item.side for item in footprints}
    for pad in pads:
        if surface_field not in pad.model_fields_set:
            raise ValueError(
                f"Native PCB schema v23+ requires explicit outer-copper centers for {pad.pad}"
            )
        footprint_reference = pad.pad.rsplit(".", 1)[0].casefold()
        footprint_side = footprint_sides.get(footprint_reference)
        if footprint_side is None:
            raise ValueError("Native PCB surface pad refers to an unobserved footprint")
        if pad.outer_copper_centers and footprint_side not in {
            item.layer for item in pad.outer_copper_centers
        }:
            raise ValueError("Native PCB pad surface centers omit their footprint side")
        for center in pad.outer_copper_centers:
            if center.layer.casefold() not in available_layers:
                raise ValueError("Native PCB outer-copper center layer is absent from the stack")
            if (center.x_nm, center.y_nm) not in pad.positions_nm:
                raise ValueError("Native PCB outer-copper center differs from its pad center")
