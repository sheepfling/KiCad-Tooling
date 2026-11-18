"""Keep Excellon tool diameters inside KiCad's signed nanometer range."""

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
    ("units", "diameter", "reason"),
    (
        ("METRIC", "0.0000001", "rounds to zero"),
        ("METRIC", "0.00000049", "rounds to zero"),
        ("INCH", "0.00000001", "rounds to zero"),
        ("METRIC", "2147.4836475", "signed nanometer range"),
        ("INCH", "1" + "0" * 302, "finite nanometer range"),
    ),
    ids=(
        "metric-underflow",
        "metric-below-half-nanometer",
        "inch-underflow",
        "int-overflow",
        "inch-scale-overflow",
    ),
)
def test_tool_diameter_outside_kicad_nanometer_range_is_unsupported(
    tmp_path: Path,
    units: str,
    diameter: str,
    reason: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    coordinates = "X12.000Y-12.000" if units == "METRIC" else "X0.4Y-0.4"
    write_pth_drill_artifact(
        fabrication,
        f"{units}\nT1C{diameter}\nT1\n{coordinates}\n",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "35"
    assert result.status == "UNSUPPORTED"
    assert reason in result.unsupported_reasons[0]
    assert result.findings == ()


@pytest.mark.parametrize(
    ("units", "diameter"),
    (
        ("METRIC", "0.0000005"),
        ("INCH", "0.00000002"),
        ("METRIC", "2147.483647"),
    ),
    ids=("half-nanometer-rounds-up", "inch-value-rounds-to-one-nanometer", "max-signed-nanometer"),
)
def test_kicad_representable_tool_diameter_remains_reviewable(
    tmp_path: Path,
    units: str,
    diameter: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    coordinates = "X12.000Y-12.000" if units == "METRIC" else "X0.4Y-0.4"
    write_pth_drill_artifact(
        fabrication,
        f"{units}\nT1C{diameter}\nT1\n{coordinates}\n",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "35"
    assert result.status == "REVIEW"
    (finding,) = result.findings
    assert finding.code == "UNBOUND_DRILL_HIT"
    assert finding.drill_evidence is not None
