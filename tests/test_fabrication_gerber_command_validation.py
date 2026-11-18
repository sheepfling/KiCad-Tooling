"""Reject partially parsed or malformed Gerber coordinate commands."""

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

_FIRST_FLASH = "X5000000Y-5000000D03*"
_MALFORMED_COMMANDS = (
    pytest.param(
        "X5000000Y-5000000BADG54D03*",
        "Gerber coordinate command",
        id="embedded-unknown-command",
    ),
    pytest.param(
        "X5000000X6000000Y-5000000D03*",
        "Gerber coordinate command",
        id="duplicate-x-axis",
    ),
    pytest.param(
        "X5000000Y-5000000Z100D03*",
        "Gerber coordinate command",
        id="unsupported-z-axis",
    ),
    pytest.param(
        "X5000000Y-5000000I100J200D01*",
        "Gerber coordinate command",
        id="unsupported-arc-offsets",
    ),
    pytest.param(
        "X5000000Y-5000000*",
        "Gerber coordinate command",
        id="missing-operation-code",
    ),
    pytest.param(
        "X5000000Y-5000000D02D03*",
        "Gerber coordinate command",
        id="duplicate-operation-code",
    ),
    pytest.param(
        "X5000000Y-5000000D03JUNK*",
        "Gerber coordinate command",
        id="operation-with-trailing-text",
    ),
    pytest.param(
        "X5000000Y-5..0D03*",
        "Gerber coordinate command",
        id="malformed-coordinate-value",
    ),
    pytest.param(
        "X5000000Y-5.0D03*",
        "Gerber coordinate command",
        id="decimal-coordinate",
    ),
    pytest.param(
        "X5000000Y-5000000D1*",
        "Gerber coordinate command",
        id="short-operation-code",
    ),
    pytest.param(
        "G1*",
        "Gerber coordinate command",
        id="short-interpolation-code",
    ),
    pytest.param(
        "X5000000Y-5000000%D03*",
        "unparsed data before a command",
        id="unmatched-percent-skips-coordinate-prefix",
    ),
)


def _rewrite_first_flash(tmp_path: Path, replacement: str) -> tuple[Path, Path, Path]:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    gerber = fabrication / "board-F_Cu.gbr"
    source = gerber.read_text(encoding="utf-8")
    first_source_flash = f"D15*{_FIRST_FLASH}"
    assert source.count(first_source_flash) == 1
    gerber.write_text(
        source.replace(first_source_flash, f"D15*{replacement}", 1),
        encoding="utf-8",
    )
    return board, fabrication, gerber


@pytest.mark.parametrize(
    "command",
    (
        "X5000000Y-5000000D03*",
        "X5000000D03*",
        "Y-5000000D03*",
        "G01X5000000Y-5000000D01*",
    ),
)
def test_supported_coordinate_command_forms_parse(tmp_path: Path, command: str) -> None:
    _, _, gerber = _rewrite_first_flash(tmp_path, command)

    layer = parse_gerber(gerber, "F.Cu")

    assert layer.features


@pytest.mark.parametrize(("command", "error_message"), _MALFORMED_COMMANDS)
def test_malformed_coordinate_commands_are_unsupported(
    tmp_path: Path, command: str, error_message: str
) -> None:
    _, _, gerber = _rewrite_first_flash(tmp_path, command)

    with pytest.raises(UnsupportedFabricationFormat, match=error_message):
        parse_gerber(gerber, "F.Cu")


def test_malformed_command_blocks_source_bound_analysis(tmp_path: Path) -> None:
    board, fabrication, _ = _rewrite_first_flash(
        tmp_path,
        "X5000000Y-5000000Z100D03*",
    )

    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(),
    )

    assert result.analyzer_version == "42"
    assert result.status == "UNSUPPORTED"
    assert "Gerber coordinate command" in result.unsupported_reasons[0]
    assert result.findings == ()
