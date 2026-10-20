"""Focused tests for the package CI driver's pytest selection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from kicad_tooling.pytest_scope import validate_test_module_files
from scripts import ci


def _selected_unit_command(
    root: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
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
    return {call.args[0]: call.args[1] for call in stage.call_args_list}["unit"]


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
def test_ci_test_module_selection_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing or outside tests"):
        validate_test_module_files(("tests/test_missing.py",), tmp_path)
