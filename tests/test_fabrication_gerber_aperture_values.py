"""Reject invalid and non-finite Gerber aperture dimensions."""

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

_CIRCULAR_APERTURE = "%ADD10C,0.500000*%"


def _rewrite_aperture(tmp_path: Path, value: str) -> tuple[Path, Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.count(_CIRCULAR_APERTURE) == 1
    gerber.write_text(
        source.replace(_CIRCULAR_APERTURE, f"%ADD10C,{value}*%", 1),
        encoding="utf-8",
    )
    return board, fabrication, gerber


@pytest.mark.parametrize(
    "value",
    (
        pytest.param("nan", id="nan"),
        pytest.param("inf", id="infinity"),
        pytest.param("-inf", id="negative-infinity"),
        pytest.param("1e309", id="decimal-overflows-double"),
        pytest.param("9" * 309, id="large-decimal-overflows-double"),
        pytest.param("0.5X", id="empty-trailing-dimension"),
        pytest.param("٠.٥", id="non-ascii-decimal-digits"),
    ),
)
def test_non_finite_aperture_values_are_unsupported(tmp_path: Path, value: str) -> None:
    _, _, gerber = _rewrite_aperture(tmp_path, value)

    with pytest.raises(UnsupportedFabricationFormat, match="aperture.*finite"):
        parse_gerber(gerber, "F.Cu")


def test_non_finite_aperture_blocks_source_bound_analysis(tmp_path: Path) -> None:
    board, fabrication, _ = _rewrite_aperture(tmp_path, "inf")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "23"
    assert result.status == "UNSUPPORTED"
    assert "aperture" in result.unsupported_reasons[0]
    assert result.findings == ()


@pytest.mark.parametrize("value", ("0.500000", ".5", "+0.5"))
def test_finite_gerber_decimal_aperture_values_remain_supported(
    tmp_path: Path,
    value: str,
) -> None:
    _, _, gerber = _rewrite_aperture(tmp_path, value)

    layer = parse_gerber(gerber, "F.Cu")

    assert layer.features
