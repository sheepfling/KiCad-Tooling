"""Reject Excellon tool diameters the analyzer cannot represent finitely."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import (
    write_pth_drill_artifact,
    write_synthetic_fabrication,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    ("diameter", "reason"),
    (
        ("9" * 400, "non-finite diameter"),
        ("1" + "0" * 307, "finite nanometer range"),
    ),
)
def test_unrepresentable_excellon_tool_diameter_is_unsupported_not_crash(
    tmp_path: Path,
    diameter: str,
    reason: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(fabrication, f"T1C{diameter}\nT1\nX12.000Y-12.000\n")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "25"
    assert result.status == "UNSUPPORTED"
    assert reason in result.unsupported_reasons[0]
    assert result.findings == ()


def test_finite_unmatched_drill_diameter_remains_reviewable(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(fabrication, "T1C0.300\nT1\nX12.000Y-12.000\n")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "25"
    assert result.status == "REVIEW"
    (finding,) = result.findings
    assert finding.code == "UNBOUND_DRILL_HIT"
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.diameter_mm == 0.3
