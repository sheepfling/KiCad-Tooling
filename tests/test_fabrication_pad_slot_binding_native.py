"""Digest-pinned KiCad coverage for oval component-pad drill slots."""

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
def test_native_oval_pad_drills_bind_to_excellon_slots(tmp_path: Path, version: str) -> None:
    board_text = _BOARD.read_text(encoding="utf-8").replace(
        "(drill 0.8)", "(drill oval 1.0 0.6)", 1
    )
    board_text = board_text.replace("(drill 1.0)", "(drill oval 0.6 1.0)", 1)
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    board = fixture_directory / _BOARD.name
    board.write_text(board_text, encoding="utf-8")

    version_result = execute_kicad_cli(
        PINNED_NATIVE_KICAD_IMAGES[version],
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-connectivity-native-version",
        fixture_directory=fixture_directory,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version

    fabrication = outputs / "oval-pad" / "fabrication"
    fabrication.mkdir(parents=True)
    export_fabrication_outputs(
        PINNED_NATIVE_KICAD_IMAGES[version],
        tmp_path,
        fixture_directory,
        fabrication,
        board,
        ("F.Cu", "B.Cu"),
    )
    pth = next(fabrication.glob("*-PTH.drl"))
    npth = next(fabrication.glob("*-NPTH.drl"))
    pth_source = pth.read_text(encoding="utf-8")
    slot_lines = [line for line in pth_source.splitlines() if "G85" in line]
    assert len(slot_lines) == 1
    plated_slots = parse_excellon(pth_source)
    nonplated_slots = parse_excellon(npth.read_text(encoding="utf-8"))
    assert len(plated_slots) == len(nonplated_slots) == 1
    assert plated_slots[0].end_mm is not None
    assert nonplated_slots[0].end_mm is not None
    assert plated_slots[0].diameter_mm == pytest.approx(0.6)
    assert nonplated_slots[0].diameter_mm == pytest.approx(0.6)

    settings = FabricationConnectivitySettings()
    clean = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)
    assert clean == repeated
    assert not clean.unsupported_reasons, clean.unsupported_reasons

    pth.write_text(
        "\n".join(line for line in pth_source.splitlines() if line != slot_lines[0]) + "\n",
        encoding="utf-8",
    )
    missing = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated_missing = analyze_fabrication_connectivity(board, fabrication, settings)
    assert missing == repeated_missing
    assert missing.status == "UNSUPPORTED"
    assert "no oval drill hit at source pad J2.1" in missing.unsupported_reasons[0]

    moved_slot = slot_lines[0].replace("Y-9.0", "Y-9.1")
    assert moved_slot != slot_lines[0]
    pth.write_text(
        "\n".join(moved_slot if line == slot_lines[0] else line for line in pth_source.splitlines())
        + "\n",
        encoding="utf-8",
    )
    moved = analyze_fabrication_connectivity(board, fabrication, settings)
    assert moved.status == "UNSUPPORTED"
    assert "no oval drill hit at source pad J2.1" in moved.unsupported_reasons[0]
