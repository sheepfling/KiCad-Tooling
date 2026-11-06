"""Ownership boundaries for named-variant PCB position exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[1]
HWREPO = ROOT / "kicad_tooling" / "hwrepo"


def _import_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        f"{'.' * node.level}{node.module or ''}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_position_export_has_one_owner_used_by_capture_and_revalidation() -> None:
    owner = HWREPO / "pcb_variant_position_export.py"
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert ".pcb_variant_position_export" in _import_modules(
        HWREPO / "pcb_variant_population_capture.py"
    )
    assert ".pcb_variant_position_export" in _import_modules(HWREPO / "cross_probe_variant.py")
    assert ".pcb_variant_population_capture" not in _import_modules(
        HWREPO / "cross_probe_variant.py"
    )
