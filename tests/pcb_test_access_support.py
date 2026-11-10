"""Shared tooling-owned requirements and snapshots for test-access tests."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbAccessProbeObservation,
    PcbPadConnectivityObservation,
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
        vias=(),
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
                    ),
                )
                if include_back
                else ()
            ),
        ),
    )


def probe_access_requirement(
    *, approach_side: Literal["front", "back", "either"]
) -> AccessAnalysis:
    requirement = access_requirement(approach_side=approach_side)
    decision = requirement.decisions[0]
    assert decision.mode == "required"
    endpoint = decision.endpoints[0].model_copy(
        update={
            "probe_envelope": AccessProbeEnvelope(
                tip_diameter_mm=0.8,
                clearance_mm=0.1,
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
