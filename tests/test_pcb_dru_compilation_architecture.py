"""Architecture boundary for the native custom-rule compilation probe."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture, pytest.mark.pcb_lint]

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "kicad_tooling/hwrepo/pcb_dru_compilation.py"
NATIVE_REPORT_OWNER = ROOT / "kicad_tooling/hwrepo/pcb_dru_compilation_native_report.py"


def test_custom_rule_compilation_owner_stays_small_and_uses_theme_owned_records() -> None:
    source = OWNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_models = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "models"
        for alias in node.names
    }

    assert len(source.splitlines()) < 500
    assert len(NATIVE_REPORT_OWNER.read_text(encoding="utf-8").splitlines()) < 500
    assert "PcbDruCompilationReport" not in imported_models
    assert "CommandEvidence" in imported_models
    assert (
        not (ROOT / "kicad_tooling/hwrepo/models.py")
        .read_text(encoding="utf-8")
        .count("PcbDruCompilationReport")
    )
