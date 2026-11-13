"""Exact-version KiCad DRC behavior for the synthetic track-angle rule."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.track_angle_rule_coverage"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-track-angle"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_TRACK_ANGLE_FIXTURES") != "1",
        reason="track-angle native fixtures require the digest-pinned KiCad lane",
    ),
]


def _run_drc(image: str, case: str, repetition: str, root: Path) -> tuple[str, ...]:
    case_root = root / f"{case}-{repetition}"
    case_root.mkdir()
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", case_root / "board.kicad_pcb")
    for name in ("board.kicad_pro", "board.kicad_dru"):
        shutil.copyfile(FIXTURES / name, case_root / name)
    report = case_root / "report.json"
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
        home_directory="kicad-track-angle",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    observed = read_native_pcb_drc_fixture_report(report)
    assert observed.kicad_version == image.split(":")[1].split("@")[0]
    return observed.violation_types


@pytest.mark.parametrize("kicad_version,image", tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_track_angle_fault_is_reported_and_collinear_control_is_clean(
    tmp_path: Path, kicad_version: str, image: str
) -> None:
    fault_first = _run_drc(image, "fault", "first", tmp_path)
    fault_repeat = _run_drc(image, "fault", "repeat", tmp_path)
    control_first = _run_drc(image, "control", "first", tmp_path)
    control_repeat = _run_drc(image, "control", "repeat", tmp_path)

    fault_angles = tuple(item for item in fault_first if item == "track_angle")
    control_angles = tuple(item for item in control_first if item == "track_angle")
    assert fault_angles, (kicad_version, fault_first)
    assert not control_angles, (kicad_version, control_first)
    assert fault_first == fault_repeat
    assert control_first == control_repeat
    assert tuple(item for item in fault_first if item != "track_angle") == tuple(
        item for item in control_first if item != "track_angle"
    )
