"""Review fabrication connectivity that changes with raster-grid phase."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
)
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _phase_sensitive_gap(tmp_path: Path) -> tuple[Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path, connected=True)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    source = source.replace(
        "%ADD11C,0.300000*%",
        "%ADD11C,0.300000*%\n%ADD12C,0.001000*%\n%ADD13C,0.010000*%",
    )
    source = source.replace("D11*X5000000Y-5000000D02*X7000000Y-5000000D01*\n", "")
    gap = (
        "D12*X5000000Y-5000000D02*X6000000Y-5000000D01*\n"
        "D12*X6085000Y-5000000D02*X7000000Y-5000000D01*\n"
        "D13*X3050000Y-5000000D03*\n"
    )
    gerber.write_text(source.replace("M02*", f"{gap}M02*", 1), encoding="utf-8")
    return board, fabrication


def test_raster_phase_check_catches_a_coarse_grid_false_pass(tmp_path: Path) -> None:
    board, fabrication = _phase_sensitive_gap(tmp_path)
    baseline = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25, check_raster_phase_stability=False),
    )
    checked = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25),
    )
    repeated = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25),
    )

    assert baseline.status == "PASS"
    assert baseline.raster_phase_check == "disabled"
    assert checked.status == "REVIEW"
    assert checked.raster_phase_check == "checked"
    assert checked.schema_version == "5"
    assert checked.analyzer_version == "40"
    assert {item.code for item in checked.findings} == {"RASTER_SENSITIVE"}
    assert {item.raster_phase for item in checked.findings} == {"x_half", "xy_half"}
    assert all(item.contacts == ("SIGNAL:J1-1", "SIGNAL:J1-2") for item in checked.findings)
    assert checked == repeated


def test_phase_sensitive_review_obeys_block_mode_and_exact_ignores(tmp_path: Path) -> None:
    board, fabrication = _phase_sensitive_gap(tmp_path)
    review = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25),
    )
    ignores = tuple(
        FabricationConnectivityIgnore(
            fingerprint=finding.fingerprint,
            reason="reviewed phase-sensitive synthetic fixture",
        )
        for finding in review.findings
    )

    blocked = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(mode="block", pixel_density=25),
    )
    ignored = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25, ignores=ignores),
    )

    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert ignored.findings == ()
    assert ignored.ignored_findings == review.findings


def test_stable_synthetic_connectivity_passes_phase_check(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, connected=True)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25),
    )

    assert result.status == "PASS"
    assert result.raster_phase_check == "checked"
    assert result.findings == ()
