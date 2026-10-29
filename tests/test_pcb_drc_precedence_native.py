"""Native KiCad custom DRC rule ordering on a synthetic board."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

FIXTURES = Path(__file__).parent / "fixtures/design_lint/drc-rule-precedence"
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


def _edge_violations(image: str, version: str, case: str, repeat: str, root: Path) -> int:
    work = root / f"{case}-{repeat}"
    work.mkdir()
    shutil.copyfile(BOARD / "fault.kicad_pcb", work / "board.kicad_pcb")
    shutil.copyfile(BOARD / "board.kicad_pro", work / "board.kicad_pro")
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
        home_directory="kicad-drc-rule-precedence",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    result = read_native_pcb_drc_fixture_report(report)
    assert result.kicad_version == version
    return sum(item == "copper_edge_clearance" for item in result.violation_types)


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_drc_rule_order_controls_mapped_edge_constraint(
    tmp_path: Path, version: str, image: str
) -> None:
    results = {
        case: tuple(
            _edge_violations(image, version, case, repeat, tmp_path) for repeat in ("a", "b")
        )
        for case in ("mapped-only", "general-last", "mapped-last")
    }
    assert results["mapped-only"][0] > 0
    assert results["general-last"] == (0, 0)
    assert results["mapped-last"][0] > 0
    assert all(first == second for first, second in results.values())
