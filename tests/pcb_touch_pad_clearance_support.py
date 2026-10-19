"""Small synthetic records for exact touch-pad clearance regressions."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbZoneFilledIslandObservation,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
    PcbTouchPadClearanceMap,
    PcbTouchPadClearanceObservation,
    PcbTouchPadClearanceRequestSet,
    PcbTouchPadClearanceRequirement,
)

BOARD_HASH = sha256(b"synthetic native pcb").hexdigest()
PROBE_HASH = sha256(b"synthetic pcb probe").hexdigest()
ZONE_UUID = "12345678-1234-5678-1234-567812345678"
FOOTPRINT = "Synthetic:Round_And_Oval_Pads"


def requirement(
    *,
    minimum_clearance_nm: int = 500_000,
    requirement_id: str = "J1-reference-copper",
    pad: str = "J1.1",
) -> PcbTouchPadClearanceRequirement:
    return PcbTouchPadClearanceRequirement(
        id=requirement_id,
        pad=pad,
        expected_pad_net="SIGNAL",
        reference_net="GND",
        layer="F.Cu",
        minimum_clearance_nm=minimum_clearance_nm,
    )


def clearance_map(*, minimum_clearance_nm: int = 500_000) -> PcbTouchPadClearanceMap:
    return PcbTouchPadClearanceMap(
        basis="Synthetic layout constraint used to verify a touch-pad copper gap",
        requirements=(requirement(minimum_clearance_nm=minimum_clearance_nm),),
    )


def netlist(*, pad_net: str = "SIGNAL") -> NetlistContract:
    return NetlistContract(
        components={"J1": ComponentContract(value="Synthetic connector", footprint=FOOTPRINT)},
        nets={pad_net: ("J1.1",)},
        component_pin_numbers={"J1": ("1",)},
    )


def native_pad_shapes_netlist() -> NetlistContract:
    """Return the synthetic source netlist for native pad-shape coverage."""
    return NetlistContract(
        components={"J1": ComponentContract(value="Synthetic touch pads", footprint=FOOTPRINT)},
        nets={"SIGNAL": ("J1.1", "J1.2", "J1.3", "J1.4", "J1.5", "J1.6")},
        component_pin_numbers={"J1": ("1", "2", "3", "4", "5", "6")},
    )


def request_hash(minimum_clearance_nm: int) -> str:
    requests = PcbTouchPadClearanceRequestSet(
        requests=(requirement(minimum_clearance_nm=minimum_clearance_nm),)
    )
    return sha256(model_json_bytes(requests)).hexdigest()


def snapshot(
    *,
    distance_nm: int = 500_000,
    board_pad_net: str | None = "SIGNAL",
    status: str = "MEASURED",
    minimum_clearance_nm: int = 500_000,
) -> PcbConnectivitySnapshot:
    """Return a minimal coherent schema-14 snapshot with one reference zone."""
    measured = status == "MEASURED"
    zone = PcbZoneObservation(
        uuid=ZONE_UUID,
        layer="F.Cu",
        name="Synthetic_GND_Fill",
        net="GND",
        filled_island_count=1 if measured else 0,
        unanchored_pad_island_indexes=(0,) if measured else (),
        filled_islands=(
            PcbZoneFilledIslandObservation(
                island_index=0,
                outline_nm=(
                    (10_000_000, 10_000_000),
                    (20_000_000, 10_000_000),
                    (20_000_000, 20_000_000),
                ),
            ),
        )
        if measured
        else (),
    )
    touch_observation = PcbTouchPadClearanceObservation(
        requirement_id="J1-reference-copper",
        pad="J1.1",
        expected_pad_net="SIGNAL",
        observed_pad_net=board_pad_net,
        reference_net="GND",
        layer="F.Cu",
        matching_zone_count=1,
        closest_zone_uuid=ZONE_UUID if measured else None,
        distance_nm=distance_nm if measured else None,
        status=status,
    )
    return PcbConnectivitySnapshot(
        schema_version="14",
        board_sha256=BOARD_HASH,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "a" * 64,
        probe_sha256=PROBE_HASH,
        zones_refilled=True,
        pads=(
            PcbPadConnectivityObservation(
                pad="J1.1",
                net=board_pad_net,
                footprint=FOOTPRINT,
                dnp=False,
                connected_pads=("J1.1",),
                connected_zones=(),
                connected_islands=(),
                connected_vias=(),
                positions_nm=((15_000_000, 15_000_000),),
            ),
        ),
        net_ties=(),
        zones=(zone,),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
        rule_areas=(),
        footprints=(
            PcbFootprintPlacementObservation(
                reference="J1",
                footprint=FOOTPRINT,
                dnp=False,
                value="Synthetic connector",
                position_nm=(15_000_000, 15_000_000),
                orientation_microdegrees=0,
                side="F.Cu",
            ),
        ),
        touch_pad_clearance_observations=(touch_observation,),
        touch_pad_clearance_requests_sha256=request_hash(minimum_clearance_nm),
    )


def coverage_report(
    *,
    authored: PcbTouchPadClearanceMap,
    entry,
    status: str | None = None,
) -> PcbTouchPadClearanceCoverageReport:
    """Build source-bound-looking coverage for candidate and report lifecycle tests."""
    from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256

    return PcbTouchPadClearanceCoverageReport(
        status=status or ("COMPLETE" if entry.status == "COMPLETE" else "INCOMPLETE"),
        mode="review",
        map_sha256=map_sha256(authored),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=BOARD_HASH,
        snapshot_path="build/design-lint/synthetic-pcb.json",
        snapshot_sha256=sha256(b"synthetic snapshot").hexdigest(),
        probe_sha256=PROBE_HASH,
        request_sha256=request_hash(authored.requirements[0].minimum_clearance_nm),
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "a" * 64,
        netlist_sha256=sha256(b"synthetic source netlist").hexdigest(),
        requirement_count=len(authored.requirements),
        entries=(entry,),
    )
