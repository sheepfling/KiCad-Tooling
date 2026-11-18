"""Review connectivity changes across supported raster resolutions."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo import fabrication_connectivity_raster
from kicad_tooling.hwrepo.fabrication_artwork import Contact, GerberLayer
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
)
from kicad_tooling.hwrepo.fabrication_connectivity_raster import RasterAnalysis, RasterPhase
from kicad_tooling.hwrepo.fabrication_excellon import DrillHit
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def _resolution_sensitive_gap(tmp_path: Path) -> tuple[Path, Path]:
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
        "D12*X6058000Y-5000000D02*X7000000Y-5000000D01*\n"
        "D13*X3050000Y-5000000D03*\n"
    )
    gerber.write_text(source.replace("M02*", f"{gap}M02*", 1), encoding="utf-8")
    return board, fabrication


def test_58_micrometer_gap_changes_connectivity_at_100_pixels_per_mm(tmp_path: Path) -> None:
    board, fabrication = _resolution_sensitive_gap(tmp_path)

    results = {
        density: analyze_fabrication_connectivity(
            board,
            fabrication,
            FabricationConnectivitySettings(
                pixel_density=density,
                check_raster_phase_stability=False,
                check_raster_resolution_stability=False,
            ),
        )
        for density in (25, 50, 100)
    }

    assert results[25].status == "PASS"
    assert results[50].status == "REVIEW"
    assert {item.code for item in results[50].findings} == {"OPEN"}
    assert results[100].status == "REVIEW"
    assert {item.code for item in results[100].findings} == {"OPEN"}


def test_resolution_check_catches_topology_changes_and_is_repeatable(tmp_path: Path) -> None:
    board, fabrication = _resolution_sensitive_gap(tmp_path)
    settings = FabricationConnectivitySettings(
        pixel_density=25,
        check_raster_phase_stability=False,
        check_raster_resolution_stability=True,
    )

    result = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)

    assert result.status == "REVIEW"
    assert result.raster_resolution_check == "checked"
    assert result.schema_version == "6"
    assert result.analyzer_version == "41"
    assert {item.code for item in result.findings} == {"RASTER_RESOLUTION_SENSITIVE"}
    assert {item.raster_density for item in result.findings} == {50, 100}
    assert all(item.contacts == ("SIGNAL:J1-1", "SIGNAL:J1-2") for item in result.findings)
    assert len({item.fingerprint for item in result.findings}) == 2
    assert result == repeated


def test_resolution_sensitive_findings_follow_block_and_exact_ignore_policy(
    tmp_path: Path,
) -> None:
    board, fabrication = _resolution_sensitive_gap(tmp_path)
    review = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            pixel_density=25,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
        ),
    )
    ignores = tuple(
        FabricationConnectivityIgnore(
            fingerprint=finding.fingerprint,
            reason="reviewed synthetic resolution-sensitive fixture",
        )
        for finding in review.findings
    )

    blocked = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            mode="block",
            pixel_density=25,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
        ),
    )
    ignored = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            pixel_density=25,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
            ignores=ignores,
        ),
    )

    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert ignored.findings == ()
    assert ignored.ignored_findings == review.findings


def test_stable_connectivity_passes_enabled_resolution_check(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, connected=True)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            pixel_density=25,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
        ),
    )

    assert result.status == "PASS"
    assert result.raster_resolution_check == "checked"
    assert result.findings == ()


def test_highest_supported_density_cannot_claim_resolution_stability(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, connected=True)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            pixel_density=100,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
        ),
    )

    assert result.status == "UNSUPPORTED"
    assert result.raster_resolution_check == "unavailable"
    assert any(
        "no supported density above 100 px/mm" in reason for reason in result.unsupported_reasons
    )


def test_pixel_budget_failure_makes_resolution_check_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board, fabrication = _resolution_sensitive_gap(tmp_path)
    analyze = fabrication_connectivity_raster.analyze_raster

    def reject_highest_density(
        layers: tuple[GerberLayer, ...],
        contacts: tuple[Contact, ...],
        drills: tuple[DrillHit, ...],
        density: int,
        phase: RasterPhase = "origin",
    ) -> RasterAnalysis:
        if density == 100:
            raise ValueError("raster exceeds the configured analyzer pixel budget")
        return analyze(layers, contacts, drills, density, phase)

    monkeypatch.setattr(fabrication_connectivity_raster, "analyze_raster", reject_highest_density)
    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            pixel_density=25,
            check_raster_phase_stability=False,
            check_raster_resolution_stability=True,
        ),
    )

    assert result.status == "UNSUPPORTED"
    assert result.raster_resolution_check == "unavailable"
    assert "RASTER_RESOLUTION_SENSITIVE" in {item.code for item in result.findings}
    assert any("100 px/mm" in reason for reason in result.unsupported_reasons)
