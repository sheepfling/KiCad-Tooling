"""Focused tests for the package CI driver's pytest selection."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import Mock

import pytest

from kicad_tooling.pytest_scope import validate_test_module_files
from scripts import ci


def _selected_unit_command(
    root: Path, monkeypatch: pytest.MonkeyPatch, arguments: Sequence[str]
) -> tuple[str, ...]:
    return _selected_stage_command(root, monkeypatch, arguments, "unit")


def _selected_stage_command(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: Sequence[str],
    selected_stage: str,
) -> tuple[str, ...]:
    monkeypatch.setattr(ci, "ROOT", root)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py", *arguments])
    monkeypatch.delenv("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", raising=False)
    stage = Mock()
    stage.return_value.stdout = str(root / "kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)
    monkeypatch.setattr(
        ci,
        "build_distributions",
        Mock(side_effect=StopIteration("stop after stage selection")),
    )
    with pytest.raises(StopIteration, match="stop after stage selection"):
        ci.main()
    return {call.args[0]: call.args[1] for call in stage.call_args_list}[selected_stage]


@pytest.mark.architecture
def test_ci_driver_uses_marker_selection_and_reports_durations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = _selected_unit_command(
        tmp_path,
        monkeypatch,
        ["--pytest-markexpr", "design_lint and interface_lint"],
    )
    assert command == (
        sys.executable,
        "-B",
        "-I",
        "-m",
        "pytest",
        "-q",
        "--durations=10",
        "-m",
        "design_lint and interface_lint",
    )


@pytest.mark.architecture
def test_ci_driver_prefers_existing_test_modules_over_marker_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = "tests/test_ci_pytest_selection.py"
    selected_file = tmp_path / selected
    selected_file.parent.mkdir(parents=True)
    selected_file.write_text("# synthetic selector target\n", encoding="utf-8")
    assert validate_test_module_files((selected,), tmp_path) == (selected,)

    command = _selected_unit_command(
        tmp_path,
        monkeypatch,
        [
            "--pytest-markexpr",
            "design_lint and interface_lint",
            "--pytest-paths",
            selected,
        ],
    )
    assert command == (
        sys.executable,
        "-B",
        "-I",
        "-m",
        "pytest",
        "-q",
        "--durations=10",
        selected,
    )


@pytest.mark.architecture
@pytest.mark.design_lint
@pytest.mark.rule_gate_integrity
def test_ci_driver_applies_catalogued_typecheck_targets_to_both_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = "kicad_tooling/hwrepo/connector_identity.py"
    target_path = tmp_path / target
    target_path.parent.mkdir(parents=True)
    target_path.write_text("\n", encoding="utf-8")

    linux = _selected_stage_command(tmp_path, monkeypatch, ["--typecheck-paths", target], "pyright")
    windows = _selected_stage_command(
        tmp_path, monkeypatch, ["--typecheck-paths", target], "windows-types"
    )

    assert linux[-1] == target
    assert windows[-3:] == ("--pythonversion", "3.11", target)
    assert "--pythonplatform" in windows


@pytest.mark.architecture
@pytest.mark.design_lint
@pytest.mark.rule_gate_integrity
def test_ci_driver_keeps_package_wide_typecheck_when_no_scope_is_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    linux = _selected_stage_command(tmp_path, monkeypatch, [], "pyright")
    windows = _selected_stage_command(tmp_path, monkeypatch, [], "windows-types")

    assert linux == (sys.executable, "-m", "pyright", "--pythonpath", sys.executable)
    assert windows == (
        sys.executable,
        "-m",
        "pyright",
        "--pythonpath",
        sys.executable,
        "--pythonplatform",
        "Windows",
        "--pythonversion",
        "3.11",
    )


@pytest.mark.architecture
def test_ci_test_module_selection_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing or outside tests"):
        validate_test_module_files(("tests/test_missing.py",), tmp_path)


@pytest.mark.parametrize("failure_stage", ("ruff-format", "ruff", "rumdl", "mdrepo"))
@pytest.mark.architecture
def test_fast_quality_gate_failure_stops_before_unit_suite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py"])
    calls: list[str] = []

    def run_stage(name: str, *_args: object, **_kwargs: object) -> Mock:
        calls.append(name)
        if name == failure_stage:
            raise RuntimeError(f"{name} failed")
        result = Mock()
        if name == "development-install":
            result.stdout = str(tmp_path / "kicad_tooling/__init__.py")
        return result

    monkeypatch.setattr(ci, "stage", run_stage)

    assert ci.main() == 1
    fast_stages = (
        "development-install",
        "ruff-format",
        "ruff",
        "alphus-module-role-boundaries",
        "alphus-shared-utility-duplication",
        "rumdl",
        "mdrepo",
    )
    expected = fast_stages[: fast_stages.index(failure_stage) + 1]
    assert calls == list(expected)
    assert "unit" not in calls
