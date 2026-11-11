"""Synthetic source rows for PCB drilled-opening evidence tests."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.pcb_connectivity_holes import PcbDrillHoleObservation
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
)


def drill_hole_fixture_rows(
    hole_id: str | None,
    shape: Literal["circle", "oval"] = "circle",
) -> tuple[
    tuple[PcbPadConnectivityObservation, ...],
    tuple[PcbFootprintPlacementObservation, ...],
    tuple[PcbDrillHoleObservation, ...],
]:
    """Return the matching pad, footprint, and hole evidence or empty controls."""
    if hole_id is None:
        return (), (), ()
    pad_uuid = "00000000-0000-0000-0000-000000000088"
    drill_size_nm = (400_000, 400_000) if shape == "circle" else (400_000, 200_000)
    return (
        (
            PcbPadConnectivityObservation(
                pad="H1.1",
                net=None,
                footprint="Synthetic:MountingHole",
                dnp=False,
                connected_pads=("H1.1",),
                connected_zones=(),
                connected_islands=(),
                connected_vias=(),
                positions_nm=((10_700_000, 10_000_000),),
            ),
        ),
        (
            PcbFootprintPlacementObservation(
                reference="H1",
                footprint="Synthetic:MountingHole",
                dnp=False,
                value="Synthetic footprint",
                position_nm=(10_700_000, 10_000_000),
                orientation_microdegrees=0,
                side="F.Cu",
            ),
        ),
        (
            PcbDrillHoleObservation(
                id=hole_id,
                kind="pad",
                pad="H1.1",
                pad_uuid=pad_uuid,
                footprint_reference="H1",
                footprint="Synthetic:MountingHole",
                position_nm=(10_700_000, 10_000_000),
                drill_size_nm=drill_size_nm,
                shape=shape,
                surfaces=("front", "back"),
            ),
        ),
    )
