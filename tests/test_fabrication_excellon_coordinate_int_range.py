"""Reject Excellon coordinates KiCad cannot retain in signed internal units."""

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
    ("units", "axis", "coordinate"),
    (
        ("METRIC", "X", "2147.4836475"),
        ("METRIC", "Y", "2147.4836475"),
        ("METRIC", "X", "-2147.4836485"),
        ("METRIC", "Y", "-2147.4836485"),
        ("INCH", "X", "84.546601"),
        ("INCH", "Y", "-84.546601"),
    ),
    ids=(
        "metric-positive-x-overflow",
        "metric-positive-y-overflow",
        "metric-negative-x-overflow",
        "metric-negative-y-overflow",
        "inch-positive-x-overflow",
        "inch-negative-y-overflow",
    ),
)
def test_coordinate_outside_kicad_signed_range_is_unsupported(
    tmp_path: Path,
    units: str,
    axis: str,
    coordinate: str,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    fields = f"X{coordinate}Y0" if axis == "X" else f"X0Y{coordinate}"
    write_pth_drill_artifact(fabrication, f"{units}\nT1C0.300\nT1\n{fields}\n")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(pixel_density=25),
    )

    assert result.status == "UNSUPPORTED"
    assert "signed nanometer range" in result.unsupported_reasons[0]
    assert result.findings == ()
    assert result.analyzer_version == "30"


@pytest.mark.parametrize(
    ("units", "coordinates", "expected"),
    (
        ("METRIC", "X2147.483647Y0", (2147.483647, 0.0)),
        ("METRIC", "X0Y-2147.483648", (0.0, -2147.483648)),
        ("METRIC", "X2147.4836474Y0", (2147.4836474, 0.0)),
        ("METRIC", "X0Y-2147.4836484", (0.0, -2147.4836484)),
        ("INCH", "X84.546600Y0", (2147.48364, 0.0)),
    ),
    ids=(
        "positive-limit-control",
        "negative-limit-control",
        "positive-rounding-boundary-control",
        "negative-rounding-boundary-control",
        "inch-unit-control",
    ),
)
def test_representable_large_coordinate_parses_without_native_overflow(
    units: str,
    coordinates: str,
    expected: tuple[float, float],
) -> None:
    (hit,) = parse_excellon(f"{units}\nT1C0.300\nT1\n{coordinates}\nM30\n")
    assert (hit.x_mm, hit.y_mm) == pytest.approx(expected)
