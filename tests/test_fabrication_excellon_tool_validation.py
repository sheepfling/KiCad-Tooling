"""Fail closed when Excellon hits lack valid tool geometry."""

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
    ("body", "reason"),
    (
        ("T9\nX12.000Y-12.000\n", "selects undefined tool T9"),
        ("T1C0.300\nX12.000Y-12.000\n", "no selected tool"),
        (
            "T1C0.300\nT1\nT0\nX12.000Y-12.000\n",
            "no selected tool",
        ),
        ("T1C0.000\nT1\nX12.000Y-12.000\n", "non-positive diameter"),
        (
            "T1C0.300\nT1C0.400\nT1\nX12.000Y-12.000\n",
            "conflicting diameter definitions",
        ),
    ),
)
def test_malformed_drill_tool_metadata_is_unsupported_not_review(
    tmp_path: Path,
    body: str,
    reason: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(fabrication, body)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.status == "UNSUPPORTED"
    assert reason in result.unsupported_reasons[0]
    assert result.findings == ()


def test_defined_unmatched_hole_remains_a_reviewable_mechanical_clue(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(
        fabrication,
        "T1C0.300\nT1C0.300\nT1\nX12.000Y-12.000\n",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.status == "REVIEW"
    (finding,) = result.findings
    assert finding.code == "UNBOUND_DRILL_HIT"
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.diameter_mm == 0.3
