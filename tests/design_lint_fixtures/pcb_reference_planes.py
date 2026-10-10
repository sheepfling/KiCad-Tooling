"""Synthetic PCB reference-plane evidence builders for lint regressions."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbReferencePlaneCoverageReport,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneFilledIslandObservation,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_reference_planes import pcb_reference_plane_entries

RULE = "pcb.reference_plane_coverage"


IMAGE = "ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64


BOARD = "a" * 64


PROBE = "c" * 64


NETLIST = "f" * 64


ZONE_GND = "00000000-0000-0000-0000-000000000001"


ZONE_OTHER = "00000000-0000-0000-0000-000000000002"


def requirement(
    *,
    net: str = "DATA",
    layer: str = "F.Cu",
    reference_net: str = "GND",
    minimum_length_um: int = 1,
    minimum_fraction: float = 0.9,
    review_excluded_short_tracks: bool = False,
    id: str = "data-reference",
) -> PcbReferencePlaneRequirement:
    return PcbReferencePlaneRequirement(
        id=id,
        basis="Synthetic explicitly mapped signal/reference-layer review",
        signal_net=net,
        signal_layers=(layer,),
        reference_net=reference_net,
        minimum_track_length_um=minimum_length_um,
        minimum_referenced_fraction=minimum_fraction,
        review_excluded_short_tracks=review_excluded_short_tracks,
    )


def mapping(*items: PcbReferencePlaneRequirement) -> PcbReferencePlaneMap:
    return PcbReferencePlaneMap(
        basis="Synthetic native copper coverage contract",
        requirements=items or (requirement(),),
    )


def zone(
    uuid: str,
    *,
    layer: str = "In1.Cu",
    net: str = "GND",
    outline: tuple[tuple[int, int], ...] = (
        (0, 0),
        (10_000_000, 0),
        (10_000_000, 10_000_000),
        (0, 10_000_000),
    ),
    holes: tuple[tuple[tuple[int, int], ...], ...] = (),
) -> PcbZoneObservation:
    return PcbZoneObservation(
        uuid=uuid,
        layer=layer,
        name=f"Synthetic {net} zone",
        net=net,
        filled_island_count=1,
        unanchored_pad_island_indexes=(0,),
        filled_islands=(
            PcbZoneFilledIslandObservation(
                island_index=0,
                outline_nm=outline,
                holes_nm=holes,
            ),
        ),
    )


def track(
    uuid_tail: str = "1",
    *,
    net: str = "DATA",
    layer: str = "F.Cu",
    start: tuple[int, int] = (0, 5_000_000),
    end: tuple[int, int] = (10_000_000, 5_000_000),
    geometry: str = "segment",
    start_vias: tuple[str, ...] = (),
    end_vias: tuple[str, ...] = (),
    start_tracks: tuple[str, ...] = (),
    end_tracks: tuple[str, ...] = (),
) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=f"00000000-0000-0000-0000-{int(uuid_tail):012d}",
        net=net,
        layer=layer,
        width_nm=250_000,
        start_nm=start,
        end_nm=end,
        geometry_kind=geometry,
        start_pads=(),
        end_pads=(),
        start_vias=start_vias,
        end_vias=end_vias,
        start_tracks=start_tracks,
        end_tracks=end_tracks,
    )


def snapshot(
    *tracks: PcbTrackObservation,
    zones: tuple[PcbZoneObservation, ...] | None = None,
    vias: tuple[PcbViaObservation, ...] = (),
    copper_layers: tuple[str, ...] = ("F.Cu", "In1.Cu", "B.Cu"),
) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        schema_version="9",
        board_sha256=BOARD,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(zone(ZONE_GND),) if zones is None else zones,
        vias=vias,
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=copper_layers,
    )


def report(specification: PcbReferencePlaneMap, observed: PcbConnectivitySnapshot):
    entries = pcb_reference_plane_entries(specification, observed)
    return PcbReferencePlaneCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=observed.board_sha256,
        snapshot_path="build/design-lint/snapshot.json",
        snapshot_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=observed.probe_sha256,
        kicad_version=observed.kicad_version,
        image=observed.image,
        netlist_sha256=NETLIST,
        entries=entries,
    )


def coach() -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-plane",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256=NETLIST,
    )
