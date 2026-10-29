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
    *,
    run_name: str | None = None,
    rules_source: str | None = None,
) -> tuple[str, ...]:
    case_root = root / (run_name or case)
    case_root.mkdir()
    for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
        source_name = case if suffix == ".kicad_pcb" else "board"
        shutil.copyfile(FIXTURES / f"{source_name}{suffix}", case_root / f"board{suffix}")
    if rules_source is not None:
        (case_root / "board.kicad_dru").write_text(rules_source, encoding="utf-8")
    report = root / f"{run_name or case}.drc.json"
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


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_drc_mechanical_rule_precedence(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    mapped = (FIXTURES / "board.kicad_dru").read_text(encoding="utf-8")
    mapped_body = mapped[mapped.index('(rule "front-mechanical-board-edge-clearance"') :]
    conditional_only = f"(version 1)\n{mapped_body}"
    ignore = (
        '(rule "unconditional-ignore" (severity ignore) '
        "(constraint physical_clearance (min 2mm)))\n"
    )
    opposite = (
        '(rule "opposite-ignore" (layer "B.Courtyard") (severity ignore) '
        "(constraint physical_clearance (min 2mm)))\n"
    )
    cases = {
        "ignore-last": f"{conditional_only}\n{ignore}",
        "mapped-last": f"(version 1)\n{ignore}{mapped_body}",
        "opposite-last": f"{conditional_only}\n{opposite}",
        "conditional-only": conditional_only,
        "small-earlier": f"(version 1)\n{ignore.replace('2mm', '0.1mm')}{mapped_body}",
        "small-opposite": f"{conditional_only}\n{opposite.replace('2mm', '0.1mm')}",
        "small-hole": (
            f"{conditional_only}\n"
            '(rule "small-hole" (constraint physical_hole_clearance (min 0.1mm)))\n'
        ),
        "large-hole": (
            f"{conditional_only}\n"
            '(rule "large-hole" (constraint physical_hole_clearance (min 2mm)))\n'
        ),
    }
    targets = {}
    for name, rules_source in cases.items():
        violations = _run_drc(image, "fault", tmp_path, run_name=name, rules_source=rules_source)
        targets[name] = {
            item
            for item in violations
            if any(word in item.casefold() for word in _TARGET_VIOLATION_WORDS)
        }
    assert not targets["ignore-last"], (kicad_version, targets)
    assert targets["mapped-last"], (kicad_version, targets)
    assert targets["opposite-last"], (kicad_version, targets)
    assert not targets["small-earlier"], (kicad_version, targets)
    assert not targets["small-opposite"], (kicad_version, targets)
    assert not targets["small-hole"], (kicad_version, targets)
    assert targets["large-hole"], (kicad_version, targets)
    assert bool(targets["conditional-only"]) == (kicad_version == "10.0.5"), (
        kicad_version,
        targets,
    )
