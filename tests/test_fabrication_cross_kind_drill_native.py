"""Exact-version KiCad tests for cross-kind drill-hit ownership."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
from kicad_tooling.hwrepo.fabrication_excellon import parse_excellon
from tests.fabrication_connectivity_native_support import export_fabrication_outputs
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_ARTIFACT_CONNECTIVITY") != "1",
        reason="native fabrication artifact checks run in the digest-pinned acceptance lane",
    ),
]

_BOARD = Path(__file__).parent / "fixtures/fabrication-connectivity/drilled-pads.kicad_pcb"


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_pad_and_coincident_via_require_distinct_pth_hits(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    board_text = _BOARD.read_text(encoding="utf-8")
    marker = "  (segment (start 5 5)"
    via = (
        '  (via (at 10 9) (size 1.6) (drill 0.8) (layers "F.Cu" "B.Cu") '
        '(net 1) (uuid "aaaaaaaa-0000-0000-0000-000000000001"))\n'
    )
    assert marker in board_text
    board = fixture_directory / "coincident-pad-via.kicad_pcb"
    board.write_text(board_text.replace(marker, via + marker, 1), encoding="utf-8")

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-cross-kind-native-version",
        fixture_directory=fixture_directory,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version

    fabrication = outputs / "coincident-pad-via" / "fabrication"
    fabrication.mkdir(parents=True)
    export_fabrication_outputs(
        image, tmp_path, fixture_directory, fabrication, board, ("F.Cu", "B.Cu")
    )
    pth = next(fabrication.glob("*-PTH.drl"))
    source = pth.read_text(encoding="utf-8")
    meaningful_lines = [
        line.strip() for line in source.splitlines() if line.strip() and not line.startswith(";")
    ]
    assert meaningful_lines[-1].upper() == "M30"
    hits = parse_excellon(source)
    assert len(hits) == 2
    assert {(hit.x_mm, hit.y_mm, hit.diameter_mm) for hit in hits} == {(10.0, -9.0, 0.8)}

    settings = FabricationConnectivitySettings()
    complete = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)
    assert complete == repeated
    assert not complete.unsupported_reasons, complete.unsupported_reasons

    hit_lines = [line for line in source.splitlines() if line.startswith("X")]
    assert len(hit_lines) == 2
    source_lines = source.splitlines()
    end_marker = next(
        index
        for index in range(len(source_lines) - 1, -1, -1)
        if source_lines[index].strip().upper() == "M30"
    )
    source_lines.insert(end_marker, hit_lines[0])
    pth.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    extra_hit = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated_extra_hit = analyze_fabrication_connectivity(board, fabrication, settings)
    assert extra_hit == repeated_extra_hit
    assert extra_hit.status == "REVIEW"
    (unbound,) = tuple(
        finding for finding in extra_hit.findings if finding.code == "UNBOUND_DRILL_HIT"
    )
    assert unbound.drill_evidence is not None
    assert unbound.drill_evidence.plating == "plated"
    assert unbound.drill_evidence.multiplicity == 1

    pth.write_text(source, encoding="utf-8")
    missing_copy = False
    retained_lines: list[str] = []
    for line in source.splitlines():
        if not missing_copy and line == hit_lines[0]:
            missing_copy = True
            continue
        retained_lines.append(line)
    assert missing_copy
    pth.write_text("\n".join(retained_lines) + "\n", encoding="utf-8")

    missing = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated_missing = analyze_fabrication_connectivity(board, fabrication, settings)
    assert missing == repeated_missing
    assert missing.status == "UNSUPPORTED"
    assert "cannot uniquely bind all source PCB pads and vias" in missing.unsupported_reasons[0]
    assert "no independent hit remains" in missing.unsupported_reasons[0]
