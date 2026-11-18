"""Exact-version native coverage checks for unsupported source land shapes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_native_support import export_fabrication_outputs
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_ARTIFACT_CONNECTIVITY") != "1",
        reason="native fabrication artifact checks run in the digest-pinned acceptance lane",
    ),
]

_FIXTURE = Path(__file__).parent / (
    "fixtures/fabrication-connectivity/multilayer/four-layer-trapezoid-land-coverage.kicad_pcb"
)
_COPPER_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
_SETTINGS = FabricationConnectivitySettings(check_raster_phase_stability=False)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_trapezoid_reports_source_coverage_gap_with_macro_limit(
    tmp_path: Path, version: str
) -> None:
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    board = fixture_directory / "board.kicad_pcb"
    board.write_text(_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    export_fabrication_outputs(
        PINNED_NATIVE_KICAD_IMAGES[version],
        tmp_path,
        fixture_directory,
        output_directory,
        board,
        _COPPER_LAYERS,
    )

    report = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)
    repeated = analyze_fabrication_connectivity(board, output_directory, _SETTINGS)

    assert report == repeated
    assert report.status == "UNSUPPORTED"
    assert report.unsupported_reasons
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.code == "SOURCE_LAND_GEOMETRY_UNREVIEWED"
    assert finding.contacts == ("J3-1",)
    assert finding.net == "SIGNAL"
    assert finding.location_mm == (13.0, -10.0)
    assert finding.land_coverage_evidence is not None
    assert finding.land_coverage_evidence.reason == "unsupported_pad_shape"
    assert finding.land_coverage_evidence.pad_shape == "trapezoid"
    assert finding.land_coverage_evidence.contact_layer == "top"
