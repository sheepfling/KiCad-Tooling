"""Native KiCad expansion of a project-specified custom-rule severity."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

FIXTURES = Path(__file__).parent / "fixtures/design_lint/drc-severity-text-variable"
BOARD = Path(__file__).parent / "fixtures/design_lint/differential-pair-edge-clearance"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _edge_evidence(
    root: Path, image: str, version: str, mode: str, repeat: str
) -> tuple[bool, ...]:
    work = root / f"{mode}-{repeat}"
    work.mkdir()
    shutil.copyfile(BOARD / "fault.kicad_pcb", work / "board.kicad_pcb")
    shutil.copyfile(FIXTURES / f"{mode}.kicad_pro", work / "board.kicad_pro")
    shutil.copyfile(FIXTURES / "board.kicad_dru", work / "board.kicad_dru")
    report = work / "report.json"
    command = execute_kicad_cli(
        image,
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            str(report),
            str(work / "board.kicad_pcb"),
        ),
        root,
        home_directory="kicad-drc-severity-variable",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    observed = read_native_pcb_drc_fixture_report(report)
    assert observed.kicad_version == version
    payload = json.loads(report.read_text(encoding="utf-8"))
    return tuple(
        bool(item.get("excluded", False))
        for item in payload["violations"]
        if item.get("type") == "copper_edge_clearance"
    )


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_project_variable_selects_custom_rule_severity(
    tmp_path: Path, version: str, image: str
) -> None:
    results = {
        mode: tuple(_edge_evidence(tmp_path, image, version, mode, repeat) for repeat in ("a", "b"))
        for mode in ("error", "ignore", "exclusion")
    }
    assert results["error"] == ((False,), (False,))
    assert results["ignore"] == ((), ())
    expected_excluded = version == "10.0.5"
    assert results["exclusion"] == ((expected_excluded,), (expected_excluded,))
