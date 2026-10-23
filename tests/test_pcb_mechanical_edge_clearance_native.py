"""Exact-version KiCad DRC regression for courtyard-to-edge clearance."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.mechanical_edge_clearance_rule_coverage"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance"
_TARGET_VIOLATION_WORDS = ("clearance", "courtyard")

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _run_drc(
    image: str,
    case: str,
    root: Path,
) -> tuple[str, ...]:
    case_root = root / case
    case_root.mkdir()
    for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
        source_name = case if suffix == ".kicad_pcb" else "board"
        shutil.copyfile(FIXTURES / f"{source_name}{suffix}", case_root / f"board{suffix}")
    report = root / f"{case}.drc.json"
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
            str(case_root / "board.kicad_pcb"),
        ),
        root,
        home_directory="kicad-mechanical-edge-clearance",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    observed = read_native_pcb_drc_fixture_report(report)
    assert observed.kicad_version == image.split(":")[1].split("@")[0]
    return observed.violation_types


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_drc_detects_clearance_fault_and_accepts_control(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    fault_types = _run_drc(image, "fault", tmp_path)
    control_types = _run_drc(image, "control", tmp_path)
    fault_target_types = {
        item
        for item in fault_types
        if any(word in item.casefold() for word in _TARGET_VIOLATION_WORDS)
    }
    control_target_types = {
        item
        for item in control_types
        if any(word in item.casefold() for word in _TARGET_VIOLATION_WORDS)
    }

    assert fault_target_types, (kicad_version, fault_types)
    assert not control_target_types, (kicad_version, control_types)
