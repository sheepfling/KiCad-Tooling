"""Validate standard Gerber aperture parameters and raster bounds."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    parse_gerber,
)
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_connectivity_raster import _canvas
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


def _write_aperture_definition(tmp_path: Path, kind: str, parameters: str) -> Path:
    gerber = tmp_path / "aperture.gbr"
    gerber.write_text(
        "\n".join(
            (
                "%FSLAX26Y26*%",
                "%MOMM*%",
                f"%ADD10{kind},{parameters}*%",
                "D10*",
                "X0Y0D03*",
                "M02*",
                "",
            )
        ),
        encoding="utf-8",
    )
    return gerber


def _add_unused_aperture(tmp_path: Path, kind: str, parameters: str) -> tuple[Path, Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.count(_CIRCULAR_APERTURE) == 1
    gerber.write_text(
        source.replace(
            _CIRCULAR_APERTURE,
            f"{_CIRCULAR_APERTURE}\n%ADD12{kind},{parameters}*%",
            1,
        ),
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

    assert result.analyzer_version == "42"
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


@pytest.mark.parametrize(
    ("kind", "parameters"),
    (
        pytest.param("R", "0.5", id="rectangle-missing-y-size"),
        pytest.param("O", "0.5", id="obround-missing-y-size"),
        pytest.param("R", "0X0.5", id="rectangle-zero-x-size"),
        pytest.param("R", "0.5X-0.25", id="rectangle-negative-y-size"),
        pytest.param("O", "0.5X0", id="obround-zero-y-size"),
        pytest.param("O", "-0.5X0.25", id="obround-negative-x-size"),
        pytest.param("P", "0X3", id="polygon-zero-diameter"),
        pytest.param("P", "-0.5X3", id="polygon-negative-diameter"),
        pytest.param("P", "0.5X2", id="polygon-too-few-vertices"),
        pytest.param("P", "0.5X13", id="polygon-too-many-vertices"),
        pytest.param("P", "0.5X2.5", id="polygon-fractional-vertices"),
        pytest.param("P", "0.5X3.0", id="polygon-decimal-vertex-token"),
        pytest.param("P", "0.5X1000000000", id="polygon-unbounded-vertices"),
    ),
)
def test_invalid_standard_aperture_parameters_are_unsupported(
    tmp_path: Path, kind: str, parameters: str
) -> None:
    gerber = _write_aperture_definition(tmp_path, kind, parameters)

    with pytest.raises(UnsupportedFabricationFormat, match="aperture"):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    ("kind", "parameters", "expected"),
    (
        pytest.param("C", "0", ("C", (0.0,)), id="zero-diameter-circle-is-valid"),
        pytest.param("R", "0.25X0.5", ("R", (0.25, 0.5)), id="rectangle"),
        pytest.param("O", "0.25X0.5", ("O", (0.25, 0.5)), id="obround"),
        pytest.param("P", "0.5X3", ("P", (0.5, 3.0)), id="triangle"),
        pytest.param(
            "P",
            "0.5X12X-30.25",
            ("P", (0.5, 12.0, -30.25)),
            id="rotated-twelve-vertex-polygon",
        ),
    ),
)
def test_supported_standard_aperture_boundaries_remain_valid(
    tmp_path: Path,
    kind: str,
    parameters: str,
    expected: tuple[str, tuple[float, ...]],
) -> None:
    gerber = _write_aperture_definition(tmp_path, kind, parameters)

    layer = parse_gerber(gerber, "F.Cu")

    assert len(layer.features) == 1
    assert layer.features[0].aperture == expected


def test_polygon_vertex_count_does_not_expand_its_physical_bounds(tmp_path: Path) -> None:
    gerber = _write_aperture_definition(tmp_path, "P", "0.5X12")
    layer = parse_gerber(gerber, "F.Cu")

    canvas = _canvas((layer,), (), (), density=10)

    assert canvas.bounds == (-1.25, -1.25, 1.25, 1.25)


def test_invalid_polygon_parameters_block_source_bound_analysis(tmp_path: Path) -> None:
    board, fabrication, _ = _add_unused_aperture(tmp_path, "P", "0.5X2.5")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "42"
    assert result.status == "UNSUPPORTED"
    assert "aperture" in result.unsupported_reasons[0]
    assert result.findings == ()
