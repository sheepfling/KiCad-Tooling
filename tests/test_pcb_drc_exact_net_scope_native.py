"""Pinned KiCad behavior for exact custom DRC net selectors without a target net."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.drc_exact_net_scope_unmatched"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-net-scope"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
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
    for name in ("board.kicad_pcb", "board.kicad_pro"):
        shutil.copyfile(FIXTURES / name, case_root / name)
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
        home_directory=f"pcb-drc-exact-net-scope-{case}-{repetition}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == image.split(":")[1].split("@")[0]
    return tuple(sorted(str(item["type"]) for item in report["violations"]))


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_exact_net_selector_case_semantics_are_deterministic(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    stale_first = _run_drc(image, "stale", "first", tmp_path)
    stale_repeat = _run_drc(image, "stale", "repeat", tmp_path)
    case_variant_first = _run_drc(image, "case-variant", "first", tmp_path)
    case_variant_repeat = _run_drc(image, "case-variant", "repeat", tmp_path)
    matched_first = _run_drc(image, "matched", "first", tmp_path)
    matched_repeat = _run_drc(image, "matched", "repeat", tmp_path)

    assert stale_first == stale_repeat, (kicad_version, stale_first, stale_repeat)
    assert case_variant_first == case_variant_repeat, (
        kicad_version,
        case_variant_first,
        case_variant_repeat,
    )
    assert matched_first == matched_repeat, (kicad_version, matched_first, matched_repeat)
    assert "track_width" not in stale_first, (kicad_version, stale_first)
    assert case_variant_first == matched_first, (
        kicad_version,
        case_variant_first,
        matched_first,
    )
    assert "track_width" in matched_first, (kicad_version, matched_first)
