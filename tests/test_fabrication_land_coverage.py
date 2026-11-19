"""Report source contacts that the standard land-flash matcher cannot verify."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
)
from kicad_tooling.hwrepo.fabrication_contact_land import source_land_assessment
from kicad_tooling.hwrepo.fabrication_contact_source import SourceComponentPad
from tests.fabrication_connectivity_support import (
    write_synthetic_fabrication,
    write_trapezoid_land_coverage_fault,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def test_source_land_assessment_reports_each_eligible_unmatched_geometry_class() -> None:
    pads = (
        SourceComponentPad(
            "J1",
            "1",
            "SIGNAL",
            "top",
            1_000_000,
            2_000_000,
            pad_shape="rect",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
        ),
        SourceComponentPad(
            "J2",
            "1",
            "SIGNAL",
            "top",
            3_000_000,
            2_000_000,
            pad_shape="trapezoid",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
        ),
        SourceComponentPad(
            "J3",
            "1",
            "SIGNAL",
            "bottom",
            5_000_000,
            2_000_000,
            pad_shape="rect",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
            has_custom_padstack=True,
        ),
        SourceComponentPad(
            "J4",
            "1",
            "SIGNAL",
            "top",
            7_000_000,
            2_000_000,
            pad_shape="oval",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
            land_rotation_mdeg=45_000,
        ),
        SourceComponentPad(
            "J5",
            "1",
            "SIGNAL",
            "top",
            9_000_000,
            2_000_000,
            pad_shape="circle",
            size_x_nm=1_200_000,
        ),
        SourceComponentPad(
            "J6",
            "1",
            "SIGNAL",
            "top",
            11_000_000,
            2_000_000,
            pad_shape="circle",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
        ),
        SourceComponentPad(
            "J7",
            "1",
            "SIGNAL",
            "through",
            13_000_000,
            2_000_000,
            drill_plating="nonplated",
            pad_shape="custom",
            size_x_nm=1_200_000,
            size_y_nm=800_000,
        ),
    )

    assessment = source_land_assessment(pads, ())

    assert tuple(item.contact for item in assessment.requirements) == ("J1-1",)
    assert tuple((item.contact, item.reason) for item in assessment.unreviewed) == (
        ("J2-1", "unsupported_pad_shape"),
        ("J3-1", "custom_padstack"),
        ("J4-1", "unsupported_rotation"),
        ("J5-1", "missing_dimensions"),
        ("J6-1", "circular_dimensions_mismatch"),
    )


def test_matching_source_contact_with_unhandled_pad_shape_no_longer_passes(
    tmp_path: Path,
) -> None:
    control_dir = tmp_path / "control"
    control_dir.mkdir()
    control_board, control_artifacts = write_synthetic_fabrication(control_dir)
    settings = FabricationConnectivitySettings(check_raster_phase_stability=False)
    control = analyze_fabrication_connectivity(control_board, control_artifacts, settings)

    assert control.status == "PASS"
    assert control.findings == ()

    fault_dir = tmp_path / "trapezoid-source"
    board, artifacts = write_trapezoid_land_coverage_fault(fault_dir)

    report = analyze_fabrication_connectivity(board, artifacts, settings)
    repeated = analyze_fabrication_connectivity(board, artifacts, settings)

    assert report == repeated
    assert report.status == "REVIEW"
    assert report.unsupported_reasons == ()
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.code == "SOURCE_LAND_GEOMETRY_UNREVIEWED"
    assert finding.contacts == ("J1-2",)
    assert finding.net == "SIGNAL"
    assert finding.location_mm == (7.0, -5.0)
    assert finding.land_coverage_evidence is not None
    assert finding.land_coverage_evidence.reason == "unsupported_pad_shape"
    assert finding.land_coverage_evidence.pad_shape == "trapezoid"
    assert finding.land_coverage_evidence.contact_layer == "top"

    blocked = analyze_fabrication_connectivity(
        board,
        artifacts,
        FabricationConnectivitySettings(mode="block", check_raster_phase_stability=False),
    )
    ignored = analyze_fabrication_connectivity(
        board,
        artifacts,
        FabricationConnectivitySettings(
            mode="block",
            check_raster_phase_stability=False,
            ignores=(
                FabricationConnectivityIgnore(
                    fingerprint=finding.fingerprint,
                    reason="synthetic review of unsupported trapezoid-land geometry",
                ),
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert ignored.ignored_findings == report.findings
