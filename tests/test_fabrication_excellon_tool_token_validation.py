"""Reject malformed, reserved, or out-of-range Excellon tool tokens."""

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
        (
            "T1C1.2.3\nT1\nX12.000Y-12.000\n",
            "malformed Excellon tool definition",
        ),
        ("T1C.\nT1\nX12.000Y-12.000\n", "malformed Excellon tool definition"),
        (
            "T1C1e2\nT1\nX12.000Y-12.000\n",
            "malformed Excellon tool definition",
        ),
        (
            "T" + "9" * 5000 + "C0.300\nT1\nX12.000Y-12.000\n",
            "exceeds the KiCad D-code range",
        ),
        (
            "T2147483638C0.300\nT1\nX12.000Y-12.000\n",
            "exceeds the KiCad D-code range",
        ),
        (
            "T0C0.300\nT0\nX12.000Y-12.000\n",
            "T0 is not a selectable drill tool",
        ),
    ),
    ids=(
        "multiple-decimal-points",
        "empty-diameter",
        "scientific-notation",
        "tool-id-digit-limit",
        "tool-id-native-range",
        "reserved-t0-definition",
    ),
)
def test_malformed_or_unselectable_tool_token_is_unsupported(
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

    assert result.analyzer_version == "40"
    assert result.status == "UNSUPPORTED"
    assert reason in result.unsupported_reasons[0]
    assert result.findings == ()


@pytest.mark.parametrize(
    "definition",
    (
        "T0001F00S00C.300F00S00",
        "T0001S0F0C.300S0F0",
    ),
    ids=("feed-spindle-before-and-after-diameter", "spindle-feed-before-and-after-diameter"),
)
def test_kicad_tool_syntax_and_t0_terminator_remain_reviewable(
    tmp_path: Path,
    definition: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    write_pth_drill_artifact(
        fabrication,
        f"{definition}\nT01\nX12.000Y-12.000\nT0\n",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "40"
    assert result.status == "REVIEW"
    (finding,) = result.findings
    assert finding.code == "UNBOUND_DRILL_HIT"
    assert finding.drill_evidence is not None
    assert finding.drill_evidence.diameter_mm == 0.3
