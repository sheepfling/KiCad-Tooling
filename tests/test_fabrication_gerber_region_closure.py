"""Reject Gerber regions whose contours are not explicitly closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_gerber,
)
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_CLOSED_TRIANGLE = """G36*
X1000000Y-1000000D02*
X2000000Y-1000000D01*
X2000000Y-2000000D01*
X1000000Y-1000000D01*
G37*
"""
_OPEN_TRIANGLE = _CLOSED_TRIANGLE.replace(
    "X1000000Y-1000000D01*\nG37*", "X1000000Y-2000000D01*\nG37*"
)


def _gerber_with_region(tmp_path: Path, region: str) -> tuple[Path, Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.count("M02*") == 1
    gerber.write_text(source.replace("M02*", f"{region}M02*", 1), encoding="utf-8")
    return board, fabrication, gerber


def test_explicitly_closed_region_contour_remains_supported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, _CLOSED_TRIANGLE)

    layer = parse_gerber(gerber, "F.Cu")

    region = layer.features[-1]
    assert region.kind == "region"
    assert len(region.points) == 4
    assert region.points[0] == region.points[-1]


def test_open_region_contour_is_unsupported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, _OPEN_TRIANGLE)

    with pytest.raises(UnsupportedFabricationFormat, match="region contour.*closed"):
        parse_gerber(gerber, "F.Cu")


def test_arc_interpolation_remains_unsupported(tmp_path: Path) -> None:
    _, _, gerber = _gerber_with_region(tmp_path, "G02*\n")

    with pytest.raises(UnsupportedFabricationFormat, match="arc or quadrant interpolation"):
        parse_gerber(gerber, "F.Cu")


def test_open_region_blocks_source_bound_connectivity(tmp_path: Path) -> None:
    board, fabrication, _ = _gerber_with_region(tmp_path, _OPEN_TRIANGLE)

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "35"
    assert result.status == "UNSUPPORTED"
    assert "region contour" in result.unsupported_reasons[0]
    assert result.findings == ()
