"""Local orchestration checks for the exact-version synthetic DRC lane."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_signal_path_drc_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import CommandEvidence, DesignLintPolicy, ProjectConfig
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

_EXPECTED_FAULTS = ("length_out_of_range", "skew_out_of_range")


def _install_mock_native_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    kicad_version: str,
    fault_types: tuple[str, ...] = _EXPECTED_FAULTS,
    ignored_types: tuple[str, ...] = (),
) -> None:
    from kicad_tooling.hwrepo import contract_coach

    monkeypatch.setattr(contract_coach, "pinned_image", lambda image: image)

    def run_command(root: Path, argv: tuple[str, ...], *, timeout: int) -> CommandEvidence:
        assert timeout == 600
        mount = next(argument for argument in argv if argument.endswith(":/output:rw"))
        output = Path(mount.rsplit(":", 2)[0])
        for case, violations in (
            ("control", ()),
            ("fault", fault_types),
            ("ignored", ignored_types),
        ):
            (output / f"{case}.kicad_pcb").write_text(f"synthetic {case} board\n", encoding="utf-8")
            (output / f"{case}.kicad_dru").write_text(f"synthetic {case} rules\n", encoding="utf-8")
            for run in ("first", "repeat"):
                report = {
                    "kicad_version": kicad_version,
                    "source": f"/output/{case}.kicad_pcb",
                    "violations": [{"type": violation} for violation in violations],
                }
                (output / f"{case}.{run}.json").write_text(json.dumps(report), encoding="utf-8")
                (output / f"{case}.{run}.exit").write_text(
                    "5\n" if case == "fault" else "0\n", encoding="utf-8"
                )
        return CommandEvidence(argv=argv, started_utc="synthetic", returncode=0)

    monkeypatch.setattr(contract_coach, "run_command", run_command)


def _copy_project(base: Path, expected_version: str) -> tuple[Path, ProjectConfig]:
    root, _ = synthetic_design_lint_project(
        base,
        DesignLintPolicy(),
        kicad_version=expected_version,
        image=PINNED_NATIVE_KICAD_IMAGES[expected_version],
    )
    config = selected_config(root, "controller")
    assert config.kicad_version == expected_version
    return root, config


@pytest.mark.parametrize(
    "kicad_version",
    tuple(PINNED_NATIVE_KICAD_IMAGES),
)
def test_native_lane_records_generated_source_and_report_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kicad_version: str,
) -> None:
    root, config = _copy_project(tmp_path, kicad_version)
    _install_mock_native_run(monkeypatch, kicad_version=kicad_version)
    log = HostedLog(root, f"signal-path-lane-{kicad_version}")

    pcb_signal_path_drc_fixture_lane(root, project="controller", image=config.image, log=log)

    result = next(
        item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage") == "pcb-signal-path-drc-fixture/native-run"
        and item.get("status") == "PASS"
    )
    output = root / result["artifact_directory"]
    for field, relative_path in (
        ("control_board_sha256", "control.kicad_pcb"),
        ("control_rules_sha256", "control.kicad_dru"),
        ("fault_board_sha256", "fault.kicad_pcb"),
        ("fault_rules_sha256", "fault.kicad_dru"),
        ("ignored_board_sha256", "ignored.kicad_pcb"),
        ("ignored_rules_sha256", "ignored.kicad_dru"),
        ("control_first_drc_sha256", "control.first.json"),
        ("control_repeat_drc_sha256", "control.repeat.json"),
        ("fault_first_drc_sha256", "fault.first.json"),
        ("fault_repeat_drc_sha256", "fault.repeat.json"),
        ("ignored_first_drc_sha256", "ignored.first.json"),
        ("ignored_repeat_drc_sha256", "ignored.repeat.json"),
    ):
        assert result[field] == digest(output / relative_path)
    assert result["control_exit_code"] == 0
    assert result["fault_exit_code"] == 5
    assert result["ignored_exit_code"] == 0
    assert result["ignored_violation_types"] == "none"
    assert result["repeatable"] == "true"


def test_native_lane_rejects_a_fault_missing_one_expected_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = "controller"
    root, config = _copy_project(tmp_path, "10.0.0")
    _install_mock_native_run(
        monkeypatch,
        kicad_version="10.0.0",
        fault_types=("length_out_of_range",),
    )
    log = HostedLog(root, "signal-path-lane-missed-fault")

    with pytest.raises(ValueError, match="missed length/skew"):
        pcb_signal_path_drc_fixture_lane(root, project=project, image=config.image, log=log)


def test_native_lane_rejects_a_custom_rule_with_ignored_severity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = "controller"
    root, config = _copy_project(tmp_path, "10.0.0")
    _install_mock_native_run(
        monkeypatch,
        kicad_version="10.0.0",
        ignored_types=("length_out_of_range",),
    )
    log = HostedLog(root, "signal-path-lane-ignored-rule-still-reports")

    with pytest.raises(ValueError, match="ignored-rule control produced target findings"):
        pcb_signal_path_drc_fixture_lane(root, project=project, image=config.image, log=log)
