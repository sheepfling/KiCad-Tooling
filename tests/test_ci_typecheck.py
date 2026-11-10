"""Focused tests for scoped Pyright command preparation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kicad_tooling.ci_typecheck import pyright_command, validate_typecheck_paths

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]


def test_typecheck_paths_are_sorted_deduplicated_and_package_scoped(tmp_path: Path) -> None:
    first = "kicad_tooling/hwrepo/first.py"
    second = "kicad_tooling/hwrepo/second.py"
    for relative in (first, second):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n", encoding="utf-8")

    assert validate_typecheck_paths((second, first, second), tmp_path) == (first, second)


@pytest.mark.parametrize(
    "target",
    (
        "tests/test_example.py",
        "kicad_tooling/../tests/test_example.py",
        "kicad_tooling/source.pyc",
        "kicad_tooling/missing.py",
        "kicad_tooling\\source.py",
    ),
)
def test_typecheck_paths_reject_missing_or_out_of_package_targets(
    tmp_path: Path, target: str
) -> None:
    with pytest.raises(ValueError, match="under kicad_tooling/"):
        validate_typecheck_paths((target,), tmp_path)


def test_pyright_commands_keep_full_scope_by_default_and_accept_selected_modules() -> None:
    target = "kicad_tooling/hwrepo/connector_identity.py"

    assert pyright_command(sys.executable) == (
        sys.executable,
        "-m",
        "pyright",
        "--pythonpath",
        sys.executable,
    )
    assert pyright_command(sys.executable, target_paths=(target,))[-1] == target
    assert pyright_command(sys.executable, target_paths=(target,), windows=True) == (
        sys.executable,
        "-m",
        "pyright",
        "--pythonpath",
        sys.executable,
        "--pythonplatform",
        "Windows",
        "--pythonversion",
        "3.11",
        target,
    )
