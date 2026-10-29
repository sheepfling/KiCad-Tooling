"""Native KiCad expands project text variables before custom DRC evaluation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

FIXTURES = Path(__file__).parent / "fixtures/design_lint/drc-text-variables"
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


def _edge_count(image: str, version: str, case: str, repeat: str, root: Path) -> int:
    work = root / f"{case}-{repeat}"
    work.mkdir()
    shutil.copyfile(BOARD / "fault.kicad_pcb", work / "board.kicad_pcb")
    shutil.copyfile(FIXTURES / "board.kicad_pro", work / "board.kicad_pro")
    shutil.copyfile(FIXTURES / f"{case}.kicad_dru", work / "board.kicad_dru")
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
        home_directory="kicad-drc-text-variables",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    observed = read_native_pcb_drc_fixture_report(report)
    assert observed.kicad_version == version
    return sum(item == "copper_edge_clearance" for item in observed.violation_types)


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_project_variables_can_override_exact_edge_rule(
    tmp_path: Path, version: str, image: str
) -> None:
    counts = {
        case: tuple(_edge_count(image, version, case, repeat, tmp_path) for repeat in ("a", "b"))
        for case in ("control", "type-override", "condition-override")
    }
    assert counts["control"][0] > 0
    assert counts["type-override"] == (0, 0)
    assert counts["condition-override"] == (0, 0)
    assert all(first == second for first, second in counts.values())
