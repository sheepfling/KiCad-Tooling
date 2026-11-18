"""Require bounded, single Gerber unit and coordinate-format headers."""

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

_BASE_RECORDS = (
    "%MOMM*%",
    "%FSLAX26Y26*%",
    "%ADD10C,0.5*%",
    "D10*",
    "X5000000Y-5000000D03*",
)


def _write_gerber(tmp_path: Path, records: tuple[str, ...]) -> Path:
    path = tmp_path / "coordinates.gbr"
    path.write_text("\n".join((*records, "M02*", "")), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "records",
    (
        pytest.param(
            tuple(record for record in _BASE_RECORDS if record != "%MOMM*%"),
            id="missing-units",
        ),
        pytest.param(
            _BASE_RECORDS[:1] + _BASE_RECORDS[:1] + _BASE_RECORDS[1:],
            id="repeated-units",
        ),
        pytest.param(
            _BASE_RECORDS[1:4] + _BASE_RECORDS[4:5] + _BASE_RECORDS[:1],
            id="units-after-first-operation",
        ),
        pytest.param(
            tuple(record for record in _BASE_RECORDS if record != "%FSLAX26Y26*%"),
            id="missing-format",
        ),
        pytest.param(
            _BASE_RECORDS[:2] + _BASE_RECORDS[2:3] + _BASE_RECORDS[1:2] + _BASE_RECORDS[3:],
            id="repeated-format",
        ),
        pytest.param(
            _BASE_RECORDS[0:1] + _BASE_RECORDS[2:5] + _BASE_RECORDS[1:2],
            id="format-after-first-operation",
        ),
        pytest.param(
            ("%MOMM*%", "%FSLAX06Y06*%", *_BASE_RECORDS[2:]),
            id="zero-integer-digits",
        ),
        pytest.param(
            ("%MOMM*%", "%FSLAX76Y76*%", *_BASE_RECORDS[2:]),
            id="too-many-integer-digits",
        ),
        pytest.param(
            ("%MOMM*%", "%FSLAX25Y25*%", *_BASE_RECORDS[2:]),
            id="non-six-decimal-precision",
        ),
        pytest.param(
            ("%MOMM*%", "%FSTAX26Y26*%", *_BASE_RECORDS[2:]),
            id="trailing-zero-omission",
        ),
        pytest.param(
            (*_BASE_RECORDS[:4], "G70*"),
            id="legacy-unit-command",
        ),
        pytest.param(
            (*_BASE_RECORDS[:4], "X123456789Y-5000000D03*"),
            id="x-coordinate-exceeds-declared-width",
        ),
        pytest.param(
            (*_BASE_RECORDS[:4], "X5000000Y-123456789D03*"),
            id="y-coordinate-exceeds-declared-width",
        ),
        pytest.param(
            (*_BASE_RECORDS[:4], "X٥000000Y-5000000D03*"),
            id="non-ascii-coordinate-digit",
        ),
    ),
)
def test_invalid_gerber_coordinate_headers_and_widths_are_unsupported(
    tmp_path: Path, records: tuple[str, ...]
) -> None:
    gerber = _write_gerber(tmp_path, records)

    with pytest.raises(UnsupportedFabricationFormat):
        parse_gerber(gerber, "F.Cu")


@pytest.mark.parametrize(
    ("unit", "format_record", "x", "expected_x_mm"),
    (
        pytest.param("MOMM", "FSLAX16Y16", "1234567", 1.234567, id="metric-min-width"),
        pytest.param("MOMM", "FSLAX46Y46", "5000000", 5.0, id="metric-common-width"),
        pytest.param("MOMM", "FSLAX26Y26", "+5000000", 5.0, id="explicit-positive-sign"),
        pytest.param("MOIN", "FSLAX26Y26", "5000000", 127.0, id="imperial"),
        pytest.param("MOMM", "FSLAX66Y66", "123456789012", 123456.789012, id="max-width"),
    ),
)
def test_supported_gerber_headers_and_declared_coordinate_boundaries_parse(
    tmp_path: Path, unit: str, format_record: str, x: str, expected_x_mm: float
) -> None:
    gerber = _write_gerber(
        tmp_path,
        (
            f"%{unit}*%",
            f"%{format_record}*%",
            "%ADD10C,0.5*%",
            "D10*",
            f"X{x}Y0D03*",
        ),
    )

    layer = parse_gerber(gerber, "F.Cu")

    assert layer.features[0].points[0][0] == pytest.approx(expected_x_mm)


@pytest.mark.parametrize("header", ("%FSLAX46Y46*%", "%MOMM*%"))
def test_missing_coordinate_header_blocks_source_bound_analysis(
    tmp_path: Path, header: str
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.count(header) == 1
    gerber.write_text(source.replace(f"{header}\n", "", 1), encoding="utf-8")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "43"
    assert result.status == "UNSUPPORTED"
    assert "declaration" in result.unsupported_reasons[0]
    assert result.findings == ()
