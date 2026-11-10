"""Shared tooling-owned requirements and snapshots for test-access tests."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbAccessProbeObservation,
    PcbFootprintPlacementObservation,
    PcbPadConnectivityObservation,
    PcbTrackObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_test_access_models import (
    ExcludedTestAccess,
    PcbAccessAnalysis,
    RequiredTestAccess,
    TestAccessAnalysis,
    TestAccessEndpointRequirement,
    TestAccessProbeEnvelope,
)

AccessAnalysis = TestAccessAnalysis
AccessEndpointRequirement = TestAccessEndpointRequirement
AccessProbeEnvelope = TestAccessProbeEnvelope


def access_requirement(
    *,
    selection: Literal["all", "any"] = "all",
    approach_side: Literal["front", "back", "either"] = "either",
) -> AccessAnalysis:
    return AccessAnalysis(
        basis="Synthetic connector pinout and factory reset access requirement",
        pcb_accessibility=AnalysisNotApplicable(
            mode="not_applicable",
            reason="Synthetic unit fixture tests the schematic stage only.",
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="reset-access",
                basis="Synthetic service procedure requires reset access",
                net="RESET_N",
                selection=selection,
                endpoints=(
                    AccessEndpointRequirement(
                        kind="programming_connector",
                        reference="J1",
                        symbol="Synthetic:DB9",
                        footprint="Connector:Dsub-9_Male",
                        pin="J1.9",
                        electrical_type="passive",
                        approach_side=approach_side,
                    ),
                ),
            ),
            ExcludedTestAccess(
                mode="not_required",
                id="high-voltage-output",
                basis="Synthetic isolation and measurement review",
                net="HV_OUT",
                reason="The node is hazardous and is intentionally excluded from routine test access.",
            ),
        ),
    )


def probe_access_snapshot(
    front_nm: int | None,
    back_nm: int | None,
    *,
    back_exposed: bool = True,
    include_back: bool = True,
    aperture_shape: Literal["circle", "oval", "rectangle", "roundrect", "unsupported"] = "circle",
    aperture_diameter_nm: int | None = 1_000_000,
    schema_version: Literal["3", "17", "18", "19"] = "3",
    courtyard_obstacle: str | None = None,
    courtyard_distance_nm: int | None = None,
    unmeasured_courtyard_footprint: str | None = None,
    unmeasured_courtyard_distance_nm: int | None = None,
    via_obstacle_id: str | None = None,
    via_obstacle_net: str | None = None,
    via_obstacle_distance_nm: int | None = None,
    via_obstacle_tented: bool | None = None,
    include_via_inventory: bool = True,
    track_obstacle_uuid: str | None = None,
    track_obstacle_net: str | None = None,
    track_obstacle_distance_nm: int | None = None,
    track_obstacle_geometry: Literal["segment", "arc"] | None = None,
    include_track_inventory: bool = True,
) -> PcbConnectivitySnapshot:
    pads = (
        PcbPadConnectivityObservation(
            pad="J1.9",
            net="RESET_N",
            footprint="Connector:Dsub-9_Male",
            dnp=False,
            connected_pads=("J1.9",),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((10_000_000, 10_000_000),),
        ),
        PcbPadConnectivityObservation(
            pad="J2.9",
            net="GND",
            footprint="Connector:Dsub-9_Male",
            dnp=False,
            connected_pads=("J2.9",),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((12_000_000, 10_000_000),),
        ),
    )
    return PcbConnectivitySnapshot(
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=pads,
        net_ties=(),
        zones=(),
        access_probe_observations=(
            PcbAccessProbeObservation(
                endpoint="J1.9",
                side="front",
                target_net="RESET_N",
                target_exposed=True,
                obstacle="J2.9" if front_nm is not None else None,
                obstacle_net="GND" if front_nm is not None else None,
                distance_nm=front_nm,
                target_aperture_shape=aperture_shape,
                target_aperture_diameter_nm=aperture_diameter_nm,
                **(
                    {
                        "courtyard_obstacle": courtyard_obstacle,
                        "courtyard_distance_nm": courtyard_distance_nm,
                        "unmeasured_courtyard_footprint": unmeasured_courtyard_footprint,
                        "unmeasured_courtyard_distance_nm": unmeasured_courtyard_distance_nm,
                    }
                    if schema_version in {"17", "18", "19"}
                    else {}
                ),
                **(
                    {
                        "via_obstacle_id": via_obstacle_id,
                        "via_obstacle_net": via_obstacle_net,
                        "via_obstacle_distance_nm": via_obstacle_distance_nm,
                        "via_obstacle_tented": via_obstacle_tented,
                    }
                    if schema_version in {"18", "19"}
                    else {}
                ),
                **(
                    {
                        "track_obstacle_uuid": track_obstacle_uuid,
                        "track_obstacle_net": track_obstacle_net,
                        "track_obstacle_distance_nm": track_obstacle_distance_nm,
                        "track_obstacle_geometry": track_obstacle_geometry,
                    }
                    if schema_version == "19"
                    else {}
                ),
            ),
            *(
                (
                    PcbAccessProbeObservation(
                        endpoint="J1.9",
                        side="back",
                        target_net="RESET_N",
                        target_exposed=back_exposed,
                        obstacle="J2.9" if back_exposed and back_nm is not None else None,
                        obstacle_net="GND" if back_exposed and back_nm is not None else None,
                        distance_nm=back_nm if back_exposed else None,
                        target_aperture_shape=aperture_shape if back_exposed else None,
                        target_aperture_diameter_nm=aperture_diameter_nm if back_exposed else None,
                        **(
                            {
                                "courtyard_obstacle": None,
                                "courtyard_distance_nm": None,
                                "unmeasured_courtyard_footprint": None,
                                "unmeasured_courtyard_distance_nm": None,
                            }
                            if schema_version in {"17", "18", "19"}
                            else {}
                        ),
                        **(
                            {
                                "via_obstacle_id": None,
                                "via_obstacle_net": None,
                                "via_obstacle_distance_nm": None,
                                "via_obstacle_tented": None,
                            }
                            if schema_version in {"18", "19"}
                            else {}
                        ),
                        **(
                            {
                                "track_obstacle_uuid": None,
                                "track_obstacle_net": None,
                                "track_obstacle_distance_nm": None,
                                "track_obstacle_geometry": None,
                            }
                            if schema_version == "19"
                            else {}
                        ),
                    ),
                )
                if include_back
                else ()
            ),
        ),
        schema_version=schema_version,
        access_probe_requests_sha256="d" * 64 if schema_version in {"17", "18", "19"} else None,
        tracks=(
            (
                PcbTrackObservation(
                    uuid=track_obstacle_uuid,
                    net=track_obstacle_net,
                    layer="F.Cu",
                    width_nm=100_000,
                    start_nm=(10_800_000, 9_000_000),
                    end_nm=(10_800_000, 11_000_000),
                    geometry_kind=track_obstacle_geometry,
                    arc_mid_nm=(10_900_000, 10_000_000)
                    if track_obstacle_geometry == "arc"
                    else None,
                    arc_length_nm=100_000 if track_obstacle_geometry == "arc" else None,
                    start_pads=(),
                    end_pads=(),
                    start_vias=(),
                    end_vias=(),
                    start_tracks=(),
                    end_tracks=(),
                ),
            )
            if track_obstacle_uuid is not None and include_track_inventory
            else ()
        ),
        copper_layers=("F.Cu", "B.Cu") if schema_version in {"17", "18", "19"} else (),
        rule_areas=(),
        vias=(
            (
                PcbViaObservation(
                    id=via_obstacle_id,
                    net=via_obstacle_net,
                    x_nm=10_800_000,
                    y_nm=10_000_000,
                    start_layer="F.Cu",
                    end_layer="B.Cu",
                    diameter_nm=600_000,
                    drill_nm=300_000,
                    kind="through",
                    multiplicity=1,
                ),
            )
            if via_obstacle_id is not None and include_via_inventory
            else ()
        ),
        footprints=(
            tuple(
                PcbFootprintPlacementObservation(
                    reference=reference,
                    footprint=footprint,
                    dnp=False,
                    value="Synthetic footprint",
                    position_nm=position,
                    orientation_microdegrees=0,
                    side="F.Cu",
                )
                for reference, footprint, position in (
                    ("J1", "Connector:Dsub-9_Male", (10_000_000, 10_000_000)),
                    ("J2", "Connector:Dsub-9_Male", (12_000_000, 10_000_000)),
                    ("U1", "Synthetic:NearbyPart", (10_500_000, 10_000_000)),
                )
            )
            if schema_version in {"17", "18", "19"}
            else ()
        ),
        touch_pad_clearance_observations=(),
        touch_pad_clearance_requests_sha256=None,
    )


def probe_access_requirement(
    *,
    approach_side: Literal["front", "back", "either"],
    courtyard_clearance_mm: float | None = None,
    via_clearance_mm: float | None = None,
    track_clearance_mm: float | None = None,
) -> AccessAnalysis:
    requirement = access_requirement(approach_side=approach_side)
    decision = requirement.decisions[0]
    assert decision.mode == "required"
    endpoint = decision.endpoints[0].model_copy(
        update={
            "probe_envelope": AccessProbeEnvelope(
                tip_diameter_mm=0.8,
                clearance_mm=0.1,
                courtyard_clearance_mm=courtyard_clearance_mm,
                via_clearance_mm=via_clearance_mm,
                track_clearance_mm=track_clearance_mm,
            )
        }
    )
    decision = decision.model_copy(update={"endpoints": (endpoint,)})
    return requirement.model_copy(
        update={
            "pcb_accessibility": PcbAccessAnalysis(basis="Synthetic surface probe envelope"),
            "decisions": (decision, *requirement.decisions[1:]),
        }
    )
