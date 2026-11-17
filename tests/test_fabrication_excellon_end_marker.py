"""Require complete terminal Excellon files for source-bound drill evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_artwork import UnsupportedFabricationFormat
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_excellon import parse_excellon
from tests.fabrication_connectivity_support import write_synthetic_fabrication

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


_VALID_EXCELLON = "M48\nMETRIC\nT1C0.300\n%\nT1\nX6.0Y-5.0\nM30\n"


def test_excellon_end_marker_is_required() -> None:
    with pytest.raises(UnsupportedFabricationFormat, match="missing terminal M30"):
        parse_excellon(_VALID_EXCELLON.removesuffix("M30\n"))


def test_commands_after_excellon_end_marker_are_unsupported() -> None:
    with pytest.raises(UnsupportedFabricationFormat, match="after the M30"):
        parse_excellon(_VALID_EXCELLON + "X7.0Y-6.0\n")


def test_excellon_comments_and_blank_lines_after_end_marker_are_allowed() -> None:
    hits = parse_excellon(_VALID_EXCELLON + "\n; exporter note\n")
    assert len(hits) == 1


def test_missing_end_marker_blocks_source_bound_drill_analysis(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, through=True)
    pth = fabrication / "board-PTH.drl"
    pth.write_text(pth.read_text(encoding="utf-8").removesuffix("M30\n"), encoding="utf-8")

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "26"
    assert result.status == "UNSUPPORTED"
    assert "missing terminal M30" in result.unsupported_reasons[0]
    assert result.findings == ()
