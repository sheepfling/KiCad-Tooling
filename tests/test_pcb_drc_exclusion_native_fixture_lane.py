"""Digest-pinned native validation of persisted PCB DRC exclusion markers."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_PCB_DRC_EXCLUSION_TOOLCHAINS
from tests.native_kicad_support import execute_kicad_cli

FIXTURES = Path(__file__).parent / "fixtures/design_lint"
BOARD_FIXTURE = FIXTURES / "differential-pair-edge-clearance"
SETTINGS_FIXTURE = FIXTURES / "pcb-drc-exclusion-native"

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


def _normalized_report(
    path: Path, version: str
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if document.get("kicad_version") != version:
        raise ValueError("Native PCB report does not identify the configured KiCad version")
    violations = tuple(
        sorted(
            (
                str(item.get("type", "")),
                str(item.get("severity", "")),
                str(item.get("comment", "")),
            )
            for item in document.get("violations", [])
        )
    )
    return tuple(document.get("included_severities", ())), violations


def _run_case(
    *, image: str, version: str, case: str, repeat: str, root: Path
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    work = root / f"{version}-{case}-{repeat}"
    inputs = work / "input"
    output = work / "output"
    inputs.mkdir(parents=True)
    output.mkdir()
    shutil.copyfile(BOARD_FIXTURE / f"{case}.kicad_pcb", inputs / "board.kicad_pcb")
    shutil.copyfile(BOARD_FIXTURE / "board.kicad_dru", inputs / "board.kicad_dru")
    shutil.copyfile(SETTINGS_FIXTURE / f"{case}.kicad_pro", inputs / "board.kicad_pro")
    report = output / "drc.json"

    command = execute_kicad_cli(
        image,
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--severity-exclusions",
            "--exit-code-violations",
            "--output",
            str(report),
            str(inputs / "board.kicad_pcb"),
        ),
        work,
        home_directory="kicad-pcb-drc-exclusions",
        fixture_directory=inputs,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode in {0, 5}, command.model_dump_json(indent=2)
    return _normalized_report(report, version)


@pytest.mark.design_lint_rule("pcb.drc_exclusion_present")
def test_native_pcb_drc_reports_saved_exclusion_markers(tmp_path: Path) -> None:
    expected_comments = {
        "Synthetic reviewed USB_D_P edge-clearance exception.",
        "Synthetic reviewed USB_D_N edge-clearance exception.",
    }
    for version, image in KICAD_10_PCB_DRC_EXCLUSION_TOOLCHAINS:
        reports = {
            case: tuple(
                _run_case(image=image, version=version, case=case, repeat=repeat, root=tmp_path)
                for repeat in ("first", "repeat")
            )
            for case in ("fault", "control")
        }
        fault, fault_repeat = reports["fault"]
        control, control_repeat = reports["control"]
        assert fault == fault_repeat
        assert control == control_repeat

        included_severities, fault_violations = fault
        assert "exclusion" in included_severities
        excluded = tuple(
            (kind, comment) for kind, _severity, comment in fault_violations if comment
        )
        assert set(excluded) == {
            ("copper_edge_clearance", comment) for comment in expected_comments
        }

        control_severities, control_violations = control
        assert "exclusion" in control_severities
        assert not any(comment for _kind, _severity, comment in control_violations)
        assert not any(
            kind == "copper_edge_clearance" for kind, _severity, _comment in control_violations
        )
