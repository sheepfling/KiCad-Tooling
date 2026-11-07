"""Small synthetic maps and snapshots for thermal-pad via coverage tests."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_thermal_via_models import (
    PcbThermalViaLayerRequirement,
    PcbThermalViaMap,
    PcbThermalViaRequirement,
)


def requirement(
    *,
    pad: str = "U1.1",
    footprint: str = "Synthetic:QFN",
    net: str = "GND",
    radius_um: int = 100,
    minimum: int = 1,
    span: tuple[str, str] = ("F.Cu", "In1.Cu"),
) -> PcbThermalViaRequirement:
    return PcbThermalViaRequirement(
        id="u1-thermal-pad",
        basis="Synthetic exposed-pad via review requirement",
        pad=pad,
        footprint=footprint,
        net=net,
        maximum_center_distance_um=radius_um,
        required_layer_spans=(
            PcbThermalViaLayerRequirement(
                start_layer=span[0], end_layer=span[1], minimum_vias=minimum
            ),
        ),
    )


def mapping(item: PcbThermalViaRequirement | None = None) -> PcbThermalViaMap:
    return PcbThermalViaMap(
        basis="Synthetic source-authored thermal-pad via screen",
        requirements=(item or requirement(),),
    )


def snapshot(
    vias: tuple[tuple[int, int, str, str, bool], ...],
    *,
    pad_net: str | None = "GND",
    footprint: str = "Synthetic:QFN",
    dnp: bool = False,
    pad_present: bool = True,
    layers: tuple[str, ...] = ("F.Cu", "In1.Cu", "B.Cu"),
) -> PcbConnectivitySnapshot:
    observations: list[PcbViaObservation] = []
    connected: list[str] = []
    for index, (x_nm, y_nm, start, end, is_connected) in enumerate(vias):
        via_id = hashlib.sha256(f"thermal-screen-via-{index}".encode()).hexdigest()
        observations.append(
            PcbViaObservation(
                id=via_id,
                net="GND",
                x_nm=x_nm,
                y_nm=y_nm,
                start_layer=start,
                end_layer=end,
                diameter_nm=600_000,
                drill_nm=300_000,
                kind="through",
                multiplicity=1,
            )
        )
        if is_connected:
            connected.append(via_id)
    pads = (
        (
            PcbPadConnectivityObservation(
                pad="U1.1",
                net=pad_net,
                footprint=footprint,
                dnp=dnp,
                connected_pads=("U1.1",),
                connected_zones=(),
                connected_islands=(),
                connected_vias=tuple(connected) if pad_net == "GND" else (),
                positions_nm=((0, 0),),
            ),
        )
        if pad_present
        else ()
    )
    return PcbConnectivitySnapshot(
        schema_version="7",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=pads,
        net_ties=(),
        zones=(),
        vias=tuple(observations),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=layers,
    )
