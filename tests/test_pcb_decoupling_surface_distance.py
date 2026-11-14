"""Layer-aware decoupling distance regressions with synthetic pad evidence."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint_pcb_decoupling_candidate_evidence import (
    PcbDecouplingFindingEvidence,
    project_pcb_decoupling_evidence,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_decoupling import pcb_decoupling_entries
from tests.pcb_decoupling_support import RULE, coverage_report, mapping, requirement, snapshot

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE),
]


def test_same_xy_on_opposite_outer_layers_uses_board_thickness() -> None:
    mapped = mapping(requirement(maximum_um=None, maximum_3d_um=1500))
    evidence = snapshot(
        distances_nm={"C1": 0},
        board_thickness_nm=1_600_000,
        surface_layers_by_pad={"C1.1": ("B.Cu",), "C1.2": ("B.Cu",)},
    )

    entry = pcb_decoupling_entries(mapped, evidence)[0]
    candidate = entry.candidates[0]

    assert entry.status == "INCOMPLETE"
    assert entry.selected_capacitors == ()
    assert candidate.distance_nm == 0
    assert candidate.distance_3d_nm == 1_600_000
    assert candidate.distance_3d_squared_nm2 == 1_600_000**2
    assert (candidate.distance_3d_ic_layer, candidate.distance_3d_capacitor_layer) == (
        "F.Cu",
        "B.Cu",
    )
    assert "1600.000 um" in " ".join(candidate.issues)


@pytest.mark.parametrize(
    ("surface_layers", "limit_um", "expected_distance_nm"),
    [
        (("B.Cu",), 1600, 1_600_000),
        (("F.Cu",), 100, 0),
        (("F.Cu", "B.Cu"), 100, 0),
    ],
    ids=("opposite-side-inclusive-boundary", "same-side", "through-layer"),
)
def test_surface_layer_controls(
    surface_layers: tuple[str, ...], limit_um: int, expected_distance_nm: int
) -> None:
    evidence = snapshot(
        distances_nm={"C1": 0},
        board_thickness_nm=1_600_000,
        surface_layers_by_pad={"C1.1": surface_layers, "C1.2": surface_layers},
    )

    entry = pcb_decoupling_entries(
        mapping(requirement(maximum_um=None, maximum_3d_um=limit_um)), evidence
    )[0]

    assert entry.status == "COMPLETE"
    assert entry.candidates[0].distance_3d_nm == expected_distance_nm
    assert entry.selected_capacitors == ("C1",)


def test_missing_native_surface_evidence_is_incomplete_when_requested() -> None:
    evidence = snapshot(distances_nm={"C1": 0})
    entry = pcb_decoupling_entries(
        mapping(requirement(maximum_um=None, maximum_3d_um=100)), evidence
    )[0]

    assert entry.status == "INCOMPLETE"
    assert entry.candidates[0].distance_3d_nm is None
    assert "outer-copper centers and board thickness" in " ".join(entry.candidates[0].issues)


def test_schema_23_requires_explicit_surface_and_thickness_evidence() -> None:
    evidence = snapshot(
        distances_nm={"C1": 0},
        board_thickness_nm=1_600_000,
        surface_layers_by_pad={"C1.1": ("B.Cu",), "C1.2": ("B.Cu",)},
    )
    incomplete = evidence.model_dump()
    incomplete["pads"][0].pop("outer_copper_centers")

    with pytest.raises(ValidationError, match="explicit outer-copper centers"):
        PcbConnectivitySnapshot.model_validate(incomplete)

    legacy_with_new_fields = evidence.model_dump()
    legacy_with_new_fields["schema_version"] = "22"
    with pytest.raises(ValidationError, match="requires native PCB schema v23"):
        PcbConnectivitySnapshot.model_validate(legacy_with_new_fields)


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("missing-thickness", "requires board-thickness evidence"),
        ("missing-outer-layer", "requires both outer copper layers"),
        ("wrong-pad-center", "differs from its pad center"),
        ("wrong-footprint-side", "omit their footprint side"),
    ],
)
def test_schema_23_rejects_inconsistent_surface_evidence(fault: str, message: str) -> None:
    evidence = snapshot(
        distances_nm={"C1": 0},
        board_thickness_nm=1_600_000,
        surface_layers_by_pad={"C1.1": ("F.Cu",), "C1.2": ("F.Cu",)},
    )
    inconsistent = evidence.model_dump()
    if fault == "missing-thickness":
        inconsistent.pop("board_thickness_nm")
    elif fault == "missing-outer-layer":
        inconsistent["copper_layers"] = ("In1.Cu", "In2.Cu")
    elif fault == "wrong-pad-center":
        inconsistent["pads"][0]["outer_copper_centers"][0]["x_nm"] += 1
    else:
        inconsistent["pads"][0]["outer_copper_centers"][0]["layer"] = "B.Cu"

    with pytest.raises(ValidationError, match=message):
        PcbConnectivitySnapshot.model_validate(inconsistent)


def test_unset_surface_limit_preserves_existing_map_fingerprint() -> None:
    legacy_map = mapping(requirement())
    legacy_json = legacy_map.model_dump_json()
    report = coverage_report(legacy_map, snapshot(), netlist_sha256="f" * 64)

    assert hashlib.sha256(legacy_json.encode("utf-8")).hexdigest() == (
        "5aa0dc983225fbbba82e4e7585083a53e18252f52692594a8ccd8bfffe7218a3"
    )
    assert report.map_sha256 == hashlib.sha256(legacy_json.encode("utf-8")).hexdigest()


def test_authored_surface_limit_participates_in_map_fingerprint() -> None:
    without_limit = mapping(requirement(maximum_um=None))
    with_limit = mapping(requirement(maximum_um=None, maximum_3d_um=1600))
    report = coverage_report(with_limit, snapshot(), netlist_sha256="f" * 64)
    old_report = coverage_report(without_limit, snapshot(), netlist_sha256="f" * 64)

    assert with_limit.model_dump_json() != without_limit.model_dump_json()
    assert report.map_sha256 != old_report.map_sha256


def test_unconfigured_surface_measurement_does_not_expand_finding_evidence() -> None:
    mapped = mapping(requirement(maximum_um=None))
    report = coverage_report(
        mapped,
        snapshot(distances_nm={"C1": 42_500}, board_thickness_nm=1_600_000),
        netlist_sha256="f" * 64,
    )
    projection = project_pcb_decoupling_evidence(
        PcbDecouplingFindingEvidence(report=report, entry=report.entries[0])
    )

    assert "maximum_layer_aware_center_distance_um" not in projection.evidence
    assert "board_thickness_nm" not in projection.evidence
    assert "layer-aware distance" not in projection.evidence["candidate_distances"][0]
