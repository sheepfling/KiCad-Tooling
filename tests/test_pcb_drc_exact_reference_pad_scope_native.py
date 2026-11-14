"""Pinned KiCad behavior for exact footprint-reference-and-pad selectors."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_exact_reference_pad_scope import RULE_ID
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-reference-pad-scope"
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
    repetition: str,
    root: Path,
    *,
    board_source: str | None = None,
) -> tuple[str, ...]:
    case_root = root / f"{case}-{repetition}"
    case_root.mkdir()
    if board_source is None:
        shutil.copyfile(BOARD, case_root / "board.kicad_pcb")
    else:
        (case_root / "board.kicad_pcb").write_text(board_source, encoding="utf-8")
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
        home_directory=f"pcb-drc-reference-pad-scope-{case}-{repetition}",
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
def test_reference_pad_selector_behavior_is_version_bounded_and_deterministic(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    for case, expected_edge_clearance in (
        ("present", kicad_version == "10.0.5"),
        ("absent-pad", False),
        ("reversed", kicad_version == "10.0.5"),
        ("case-reference", kicad_version == "10.0.5"),
    ):
        first = _run_drc(image, case, "first", tmp_path)
        repeat = _run_drc(image, case, "repeat", tmp_path)
        assert first == repeat, (kicad_version, case, first, repeat)
        assert ("copper_edge_clearance" in first) is expected_edge_clearance, (
            kicad_version,
            case,
            first,
        )


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_pad_number_case_matching_is_version_bounded(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    board_source = BOARD.read_text(encoding="utf-8").replace('(pad "1" smd', '(pad "A1" smd')
    assert board_source != BOARD.read_text(encoding="utf-8")
    expected = kicad_version == "10.0.5"
    for case in ("pad-uppercase", "pad-lowercase"):
        first = _run_drc(image, case, "first", tmp_path, board_source=board_source)
        repeat = _run_drc(image, case, "repeat", tmp_path, board_source=board_source)
        assert first == repeat, (kicad_version, case, first, repeat)
        assert ("copper_edge_clearance" in first) is expected, (
            kicad_version,
            case,
            first,
        )
