"""Source matching for plated Excellon via drill hits."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_excellon import DrillHit, parse_excellon
from kicad_tooling.hwrepo.fabrication_via_binding import SourceVia, source_board_vias
from kicad_tooling.hwrepo.fabrication_via_drill_binding import (
    require_excellon_source_via_drills,
)
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_BOARD = Path(__file__).parent / "fixtures/fabrication-connectivity/via.kicad_pcb"


def _excellon(hit: str, diameter: str = "0.300") -> tuple[DrillHit, ...]:
    text = (
        "M48\n; #@! TF.FileFunction,Plated,1,2,PTH\nMETRIC\n"
        f"T1C{diameter}\n%\nG90\nG05\nT1\n{hit}\nM30\n"
    )
    return parse_excellon(text)


def test_source_via_drill_matches_native_xy_orientation_and_tool_size() -> None:
    source = source_board_vias(_BOARD.read_text(encoding="utf-8"))
    drills = _excellon("X6.0Y-5.0")

    require_excellon_source_via_drills(source, drills)
    assert drills[0].coordinate_resolution_nm == 100_000
    assert drills[0].diameter_resolution_nm == 1_000


@pytest.mark.parametrize(
    ("hit", "diameter", "reason"),
    [
        ("", "0.300", "no circular drill hit"),
        ("X6.1Y-5.0", "0.300", "no circular drill hit"),
        ("X6.0Y-5.0", "0.400", "drill diameter"),
    ],
    ids=("missing", "displaced", "wrong-diameter"),
)
def test_missing_displaced_or_wrong_size_via_drill_fails_closed(
    hit: str, diameter: str, reason: str
) -> None:
    source = source_board_vias(_BOARD.read_text(encoding="utf-8"))

    with pytest.raises(UnsupportedFabricationFormat, match=reason):
        require_excellon_source_via_drills(source, _excellon(hit, diameter))


def test_source_via_drill_rounding_uses_exported_coordinate_precision() -> None:
    source = (SourceVia("SIGNAL", 6_050_000, 5_000_000, 300_000),)

    require_excellon_source_via_drills(source, _excellon("X6.0Y-5.0"))


@pytest.mark.parametrize(
    (
        "header",
        "units",
        "tool",
        "coordinates",
        "coordinate_precision_nm",
        "diameter_precision_nm",
    ),
    (
        ("3:3", "METRIC,LZ", "0.300", "X006000Y-005000", 1_000, 1_000),
        ("2:4", "INCH,LZ", "0.011811", "X002362Y-001969", 2_540, 25),
    ),
    ids=("metric-fixed-width", "inch-fixed-width"),
)
def test_fixed_width_excellon_precision_binds_source_via(
    header: str,
    units: str,
    tool: str,
    coordinates: str,
    coordinate_precision_nm: int,
    diameter_precision_nm: int,
) -> None:
    source = (SourceVia("SIGNAL", 6_000_000, 5_000_000, 300_000),)
    text = f"M48\n; FILE_FORMAT={header}\n{units}\nT1C{tool}\n%\nT1\n{coordinates}\nM30\n"
    drills = parse_excellon(text)

    require_excellon_source_via_drills(source, drills)
    assert drills[0].coordinate_resolution_nm == coordinate_precision_nm
    assert drills[0].diameter_resolution_nm == diameter_precision_nm


def test_slot_hit_does_not_satisfy_a_circular_source_via() -> None:
    source = source_board_vias(_BOARD.read_text(encoding="utf-8"))
    slot = parse_excellon("M48\nMETRIC\nT1C0.300\n%\nG90\nG05\nT1\nX6.0Y-5.0G85X6.1Y-5.0\nM30\n")

    assert slot[0].end_mm is not None
    with pytest.raises(UnsupportedFabricationFormat, match="no circular drill hit"):
        require_excellon_source_via_drills(source, slot)


def test_analyzer_requires_source_via_drill_hit_before_rasterization(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, through=True)
    clean = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())
    (fabrication / "board-PTH.drl").unlink()
    missing = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings()
    )

    assert clean.status == "PASS"
    assert not clean.findings
    assert missing.status == "UNSUPPORTED"
    assert "no circular drill hit" in missing.unsupported_reasons[0]


@pytest.mark.parametrize(
    ("source_text", "replacement", "reason"),
    (
        ("T1C0.3", "T1C0.4", "drill diameter"),
        ("X6.0Y-5.0", "X6.1Y-5.0", "no circular drill hit"),
    ),
    ids=("wrong-diameter", "displaced-hit"),
)
def test_analyzer_rejects_wrong_size_or_displaced_pth_via(
    tmp_path: Path, source_text: str, replacement: str, reason: str
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, through=True)
    drill = fabrication / "board-PTH.drl"
    original = drill.read_text(encoding="utf-8")
    drill.write_text(original.replace(source_text, replacement), encoding="utf-8")

    report = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert report.status == "UNSUPPORTED"
    assert reason in report.unsupported_reasons[0]
