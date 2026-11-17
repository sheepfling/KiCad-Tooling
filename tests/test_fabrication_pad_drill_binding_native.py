"""Digest-pinned KiCad coverage for component-pad Excellon binding."""

from __future__ import annotations

import os
import shutil
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
def test_native_source_drilled_pads_bind_to_pth_and_npth_exports(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    board = fixture_directory / _BOARD.name
    shutil.copyfile(_BOARD, board)

    version_result = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory="fabrication-connectivity-native-version",
        fixture_directory=fixture_directory,
        output_directory=outputs,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == version

    fabrication = outputs / "drilled-pads" / "fabrication"
    fabrication.mkdir(parents=True)
    export_fabrication_outputs(
        image, tmp_path, fixture_directory, fabrication, board, ("F.Cu", "B.Cu")
    )
    pth = next(fabrication.glob("*-PTH.drl"))
    npth = next(fabrication.glob("*-NPTH.drl"))
    assert len(parse_excellon(pth.read_text(encoding="utf-8"))) == 1
    assert len(parse_excellon(npth.read_text(encoding="utf-8"))) == 1

    settings = FabricationConnectivitySettings()
    clean = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)
    assert clean == repeated
    assert not clean.unsupported_reasons, clean.unsupported_reasons

    pth_source = pth.read_text(encoding="utf-8")
    pth_lines = pth_source.splitlines()
    hits = [line for line in pth_lines if line.startswith("X")]
    assert len(hits) == 1
    pth.write_text("\n".join(line for line in pth_lines if line != hits[0]) + "\n")
    missing_plated = analyze_fabrication_connectivity(board, fabrication, settings)
    assert missing_plated.status == "UNSUPPORTED"
    assert "no circular drill hit at source pad J2.1" in missing_plated.unsupported_reasons[0]
    pth.write_text(pth_source, encoding="utf-8")

    npth.unlink()
    missing_nonplated = analyze_fabrication_connectivity(board, fabrication, settings)
    assert missing_nonplated.status == "UNSUPPORTED"
    assert "no circular drill hit at source pad J2.2" in missing_nonplated.unsupported_reasons[0]
