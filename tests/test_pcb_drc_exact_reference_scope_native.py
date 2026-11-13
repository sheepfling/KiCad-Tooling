"""Pinned KiCad behavior for exact custom DRC footprint-reference selectors."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.drc_exact_reference_scope_unmatched"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-reference-scope"
BOARD = (
    Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance/control.kicad_pcb"
)
PROJECT = (
    Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance/board.kicad_pro"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _run_drc(image: str, case: str, repetition: str, root: Path) -> tuple[str, ...]:
    case_root = root / f"{case}-{repetition}"
    case_root.mkdir()
    shutil.copyfile(BOARD, case_root / "board.kicad_pcb")
    shutil.copyfile(PROJECT, case_root / "board.kicad_pro")
    shutil.copyfile(FIXTURES / f"{case}.kicad_dru", case_root / "board.kicad_dru")
    report_path = case_root / "report.json"
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
            str(report_path),
            str(case_root / "board.kicad_pcb"),
        ),
        root,
        home_directory=f"pcb-drc-reference-scope-{case}-{repetition}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == image.split(":")[1].split("@")[0]
    return tuple(
        sorted(
            str(item["type"])
            for item in report["violations"]
            if item["type"] == "copper_edge_clearance"
        )
    )


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_exact_reference_selector_behavior_is_version_bounded_and_deterministic(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    for case, expected_edge_clearance in (
        ("absent", False),
        ("present", kicad_version == "10.0.5"),
        ("case-variant", kicad_version == "10.0.5"),
    ):
        first = _run_drc(image, case, "first", tmp_path)
        repeat = _run_drc(image, case, "repeat", tmp_path)
        assert first == repeat, (kicad_version, case, first, repeat)
        assert ("copper_edge_clearance" in first) is expected_edge_clearance, (
            kicad_version,
            case,
            first,
        )
