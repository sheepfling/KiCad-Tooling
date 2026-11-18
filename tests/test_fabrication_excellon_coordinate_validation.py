"""Reject malformed or unrepresentable Excellon coordinates as unsupported."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_excellon import parse_excellon
from tests.fabrication_connectivity_support import (
    write_pth_drill_artifact,
    write_synthetic_fabrication,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    ("coordinates", "reason"),
    (
        ("X" + "9" * 400 + "Y0", "cannot be represented"),
        ("X" + "9" * 400 + ".0Y0", "non-finite"),
        ("X1" + "0" * 307 + "Y0", "finite nanometer range"),
        ("X0." + "0" * 400 + "1Y0", "underflows"),
        ("X1.2.3Y0", "malformed"),
        ("X1e2Y0", "malformed"),
        ("X1X2Y0", "repeated"),
        ("X1.0Y1.0G85X2.0Y2.0E", "malformed"),
        ("X1.0Y1.0G85X2.0Y2.0G85X3.0Y3.0", "multiple G85"),
        ("; FILE_FORMAT=30:3\nX006000Y005000", "FILE_FORMAT"),
        ("; FILE_FORMAT=3:9\nX006000Y005000", "FILE_FORMAT"),
        (
            "; FILE_FORMAT=3:3\n; FILE_FORMAT=3:3\nX006000Y005000",
            "multiple FILE_FORMAT",
        ),
    ),
    ids=(
        "fixed-width-overflow",
        "decimal-infinity",
        "nanometer-overflow",
        "decimal-underflow",
        "malformed-decimal",
        "ignored-exponent-suffix",
        "duplicate-axis",
        "malformed-slot-end",
        "duplicate-slot-separator",
        "multi-digit-format-field",
        "unsupported-fraction-precision",
        "duplicate-format-declaration",
    ),
)
def test_unrepresentable_or_malformed_coordinate_is_unsupported(
    tmp_path: Path,
    coordinates: str,
    reason: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(fabrication, f"T1C0.300\nT1\n{coordinates}\n")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "29"
    assert result.status == "UNSUPPORTED"
    assert reason in result.unsupported_reasons[0]
    assert result.findings == ()


def test_valid_unmatched_excellon_coordinates_remain_reviewable(tmp_path: Path) -> None:
    (hit,) = parse_excellon("M48\nMETRIC\nT1C0.300\n%\nT1\nX12.000Y-12.000\nM30\n")
    assert (hit.x_mm, hit.y_mm) == (12.0, -12.0)

    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(fabrication, "T1C0.300\nT1\nX12.000Y-12.000\n")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "29"
    assert result.status == "REVIEW"
    (finding,) = result.findings
    assert finding.code == "UNBOUND_DRILL_HIT"
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.start_mm == (12.0, 12.0)
