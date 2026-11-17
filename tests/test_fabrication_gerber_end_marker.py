"""Require complete terminal Gerber files for source-bound copper evidence."""

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


_VALID_GERBER = (
    "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.500000*%\n%LPD*%\nD10*\nX1000000Y1000000D03*\nM02*\n"
)


def _write_gerber(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_gerber_end_marker_is_required(tmp_path: Path) -> None:
    path = _write_gerber(tmp_path / "layer.gbr", _VALID_GERBER.removesuffix("M02*\n"))

    with pytest.raises(UnsupportedFabricationFormat, match="missing terminal M02"):
        parse_gerber(path, "F.Cu")


def test_commands_after_gerber_end_marker_are_unsupported(tmp_path: Path) -> None:
    path = _write_gerber(tmp_path / "layer.gbr", _VALID_GERBER + "D10*\n")

    with pytest.raises(UnsupportedFabricationFormat, match="after M02"):
        parse_gerber(path, "F.Cu")


def test_duplicate_gerber_end_markers_are_unsupported(tmp_path: Path) -> None:
    path = _write_gerber(tmp_path / "layer.gbr", _VALID_GERBER + "M02*\n")

    with pytest.raises(UnsupportedFabricationFormat, match="multiple M02"):
        parse_gerber(path, "F.Cu")


def test_data_after_gerber_end_marker_is_unsupported(tmp_path: Path) -> None:
    path = _write_gerber(tmp_path / "layer.gbr", _VALID_GERBER + "unparsed bytes")

    with pytest.raises(UnsupportedFabricationFormat, match="data after the M02"):
        parse_gerber(path, "F.Cu")


def test_whitespace_after_gerber_end_marker_is_allowed(tmp_path: Path) -> None:
    path = _write_gerber(tmp_path / "layer.gbr", _VALID_GERBER + " \n\t")

    layer = parse_gerber(path, "F.Cu")

    assert len(layer.features) == 1


def test_missing_gerber_end_marker_blocks_source_bound_analysis(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    assert source.endswith("M02*\n")
    gerber.write_text(source.removesuffix("M02*\n"), encoding="utf-8")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "21"
    assert result.status == "UNSUPPORTED"
    assert "missing terminal M02" in result.unsupported_reasons[0]
    assert result.findings == ()
