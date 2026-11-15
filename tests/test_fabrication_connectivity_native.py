"""Exact-version native artifact regressions for fabrication connectivity."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import FabricationConnectivitySettings
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

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_EXPECTED = {
    "clean": ("PASS", set()),
    "isolated": ("PASS", set()),
    "open": ("REVIEW", {"OPEN"}),
    "short": ("REVIEW", {"SHORT"}),
    "via": ("PASS", set()),
}


def _run(
    image: str,
    work: Path,
    fixture_directory: Path,
    output_directory: Path,
    board: Path,
    arguments: tuple[str, ...],
) -> None:
    command = execute_kicad_cli(
        image,
        ("kicad-cli", *arguments, str(board)),
        work,
        home_directory="fabrication-connectivity-native",
        fixture_directory=fixture_directory,
        output_directory=output_directory,
    )
    assert command.returncode == 0, command.stderr
    assert command.error is None


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_gerber_ipc356_connectivity_fault_controls_repeat(
    tmp_path: Path, version: str
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
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

    for name, (expected_status, expected_codes) in _EXPECTED.items():
        board = fixture_directory / f"{name}.kicad_pcb"
        shutil.copyfile(_FIXTURES / board.name, board)
        fabrication = outputs / name / "fabrication"
        fabrication.mkdir(parents=True)
        _run(
            image,
            tmp_path,
            fixture_directory,
            fabrication,
            board,
            (
                "pcb",
                "export",
                "gerbers",
                "--layers",
                "F.Cu,B.Cu",
                "--no-protel-ext",
                "--check-zones",
                "--output",
                str(fabrication),
            ),
        )
        _run(
            image,
            tmp_path,
            fixture_directory,
            fabrication,
            board,
            (
                "pcb",
                "export",
                "drill",
                "--format",
                "excellon",
                "--excellon-separate-th",
                "--drill-origin",
                "absolute",
                "--excellon-units",
                "mm",
                "--output",
                str(fabrication),
            ),
        )
        _run(
            image,
            tmp_path,
            fixture_directory,
            fabrication,
            board,
            ("pcb", "export", "ipcd356", "--output", str(fabrication / "board.d356")),
        )

        first = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        repeated = analyze_fabrication_connectivity(
            board, fabrication, FabricationConnectivitySettings()
        )
        assert first == repeated
        assert (first.status, {item.code for item in first.findings}) == (
            expected_status,
            expected_codes,
        )

        if name == "via":
            (fabrication / "via-PTH.drl").unlink()
            missing_drill = analyze_fabrication_connectivity(
                board, fabrication, FabricationConnectivitySettings()
            )
            assert {item.code for item in missing_drill.findings} == {"NO_DRILL", "OPEN"}
