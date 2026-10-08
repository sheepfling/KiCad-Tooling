"""Exact-version native DRC fixtures for mapped signal-path rules."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_signal_path_drc_fixture_lane
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
    reason="native PCB fixtures run in the digest-pinned package acceptance lane",
)


def _retain_native_receipt(project_root: Path, log: HostedLog, project: str) -> Path:
    """Copy synthetic native evidence into the package gate's uploaded build tree."""
    scratch_dirs = tuple(
        path for path in log.directory.glob("pcb-signal-path-drc-*") if path.is_dir()
    )
    if len(scratch_dirs) > 1:
        raise ValueError(
            f"Expected at most one native signal-path scratch directory, got {scratch_dirs}"
        )
    scratch = scratch_dirs[0] if scratch_dirs else None
    source_output = scratch / "output" if scratch is not None else None
    destination = SOURCE_ROOT / "build/ci/native-fixtures/pcb-signal-path" / project
    if destination.is_symlink():
        raise ValueError("Native signal-path receipt destination cannot be a symlink")
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "output").mkdir(parents=True)
    fixture_root = SOURCE_ROOT / "tests/fixtures/design_lint/signal-path"
    replacements = [
        (str(fixture_root.resolve()), "<fixture-root>"),
        (str(project_root.resolve()), "<project-root>"),
    ]
    if source_output is not None:
        replacements.insert(0, (str(source_output.resolve()), "<output-root>"))

    expected_files = ("kicad-version.txt",)
    for case in ("control", "fault", "ignored"):
        expected_files += (f"{case}.kicad_pcb", f"{case}.kicad_dru")
        expected_files += tuple(
            f"{case}.{suffix}.{extension}"
            for suffix in ("first", "repeat")
            for extension in ("json", "exit")
        )
    if source_output is not None:
        for name in expected_files:
            source = source_output / name
            if source.is_file():
                shutil.copy2(source, destination / "output" / name)

    command_path = scratch / "native.command.json" if scratch is not None else None
    if command_path is not None and command_path.is_file():
        command = json.loads(command_path.read_text(encoding="utf-8"))

        def normalize(value: object) -> object:
            if isinstance(value, str):
                for previous, current in replacements:
                    value = value.replace(previous, current)
                return value
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            return value

        normalized_command = normalize(command)
        (destination / "native.command.json").write_text(
            json.dumps(normalized_command, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    event_values = [
        json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
    ]
    relative_output = (destination / "output").relative_to(SOURCE_ROOT).as_posix()
    relative_command = (destination / "native.command.json").relative_to(SOURCE_ROOT).as_posix()
    for event in event_values:
        for key, value in tuple(event.items()):
            if isinstance(value, str):
                for previous, current in replacements:
                    value = value.replace(previous, current)
                event[key] = value
        if event.get("stage") == "pcb-signal-path-drc-fixture/native-run":
            if source_output is not None and source_output.is_dir():
                event["artifact_directory"] = relative_output
            else:
                event.pop("artifact_directory", None)
            if (destination / "native.command.json").is_file():
                event["command_receipt"] = relative_command
                event["command_receipt_sha256"] = digest(destination / "native.command.json")
            else:
                event.pop("command_receipt", None)
            event["fixture_generator_sha256"] = digest(
                SOURCE_ROOT / "tests/fixtures/design_lint/signal-path/create.py"
            )
    (destination / "events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in event_values),
        encoding="utf-8",
    )
    return destination


@pytest.mark.parametrize(
    ("kicad_version", "image"),
    tuple(PINNED_NATIVE_KICAD_IMAGES.items()),
)
def test_native_from_to_length_and_skew_faults_are_repeatable(
    tmp_path: Path, kicad_version: str, image: str
) -> None:
    project = f"signal-path-{kicad_version.replace('.', '-')}"
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=kicad_version,
        image=image,
    )

    log = HostedLog(root, f"native-pcb-signal-path-{project}")
    try:
        pcb_signal_path_drc_fixture_lane(root, project=project, image=image, log=log)
    finally:
        receipt_directory = _retain_native_receipt(root, log, project)

    result = next(
        item
        for item in (json.loads(line) for line in log.events.read_text().splitlines())
        if item.get("stage") == "pcb-signal-path-drc-fixture/native-run"
        and item.get("status") == "PASS"
    )
    output = root / result["artifact_directory"]
    expected_findings = {"length_out_of_range", "skew_out_of_range"}
    control = set(result["control_violation_types"].split(",")) - {""}
    fault = set(result["fault_violation_types"].split(",")) - {""}
    ignored = set(result["ignored_violation_types"].split(",")) - {""}
    assert result["kicad_version"] == kicad_version
    assert result["repeatable"] == "true"
    assert not expected_findings & control
    assert expected_findings <= fault
    assert not expected_findings & ignored
    assert result["ignored_exit_code"] == 0
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

    retained_events = tuple(
        json.loads(line)
        for line in (receipt_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    )
    retained_result = next(
        item
        for item in retained_events
        if item.get("stage") == "pcb-signal-path-drc-fixture/native-run"
        and item.get("status") == "PASS"
    )
    retained_output = SOURCE_ROOT / retained_result["artifact_directory"]
    assert retained_result["kicad_version"] == kicad_version
    assert retained_result["control_first_drc_sha256"] == digest(
        retained_output / "control.first.json"
    )
    assert retained_result["fault_first_drc_sha256"] == digest(retained_output / "fault.first.json")
    assert retained_result["ignored_first_drc_sha256"] == digest(
        retained_output / "ignored.first.json"
    )
    command_receipt = SOURCE_ROOT / retained_result["command_receipt"]
    assert retained_result["command_receipt_sha256"] == digest(command_receipt)
    serialized_command = command_receipt.read_text(encoding="utf-8")
    assert "<fixture-root>" in serialized_command
    assert "<output-root>" in serialized_command
    assert str(SOURCE_ROOT.resolve()) not in serialized_command
    assert str(root.resolve()) not in serialized_command
