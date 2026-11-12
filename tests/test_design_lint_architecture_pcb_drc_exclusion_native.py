"""Keep native PCB DRC exclusion evidence in its focused owner module."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.architecture,
]

_ROOT = Path(__file__).parents[1]
_NATIVE = _ROOT / "kicad_tooling/hwrepo/pcb_drc_exclusion_native.py"
_REPORT_PARSER = _ROOT / "kicad_tooling/hwrepo/native_drc_findings.py"
_REVIEW = _ROOT / "kicad_tooling/hwrepo/pcb_drc_exclusion_review.py"
_INSPECTION = _ROOT / "kicad_tooling/hwrepo/design_lint_project_inspection.py"
_TEST = _ROOT / "tests/test_pcb_drc_exclusion_native_matching.py"


def test_exclusion_native_owner_and_regression_suite_stay_below_review_limit() -> None:
    assert len(_NATIVE.read_text(encoding="utf-8").splitlines()) < 500
    assert len(_REPORT_PARSER.read_text(encoding="utf-8").splitlines()) < 500
    assert len(_TEST.read_text(encoding="utf-8").splitlines()) < 500


def test_native_exclusion_evidence_uses_typed_sources_and_no_cli_side_effects() -> None:
    native_tree = ast.parse(_NATIVE.read_text(encoding="utf-8"))
    modules = {node.module for node in native_tree.body if isinstance(node, ast.ImportFrom)}
    assert "contracts" in modules
    assert "native_drc_findings" in modules
    assert "native_project_validation_models" in modules
    assert "pcb_drc_project_settings" in modules
    assert "subprocess" not in modules
    assert "docker" not in modules
    assert "json" not in modules

    review_tree = ast.parse(_REVIEW.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ImportFrom) and node.module == "pcb_drc_exclusion_native"
        for node in review_tree.body
    )
    inspection_tree = ast.parse(_INSPECTION.read_text(encoding="utf-8"))
    source = _INSPECTION.read_text(encoding="utf-8")
    assert "native_summary=native_summary" in source
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "source_bound_pcb_drc_exclusion_candidates"
        for node in ast.walk(inspection_tree)
    )


def test_active_rule_catalog_points_to_exclusion_native_owner() -> None:
    catalog = json.loads(
        (_ROOT / "kicad_tooling/hwrepo/design-lint-rules.json").read_text(encoding="utf-8")
    )
    rule = next(item for item in catalog["rules"] if item["rule_id"] == "pcb.drc_exclusion_present")

    assert (
        "kicad_tooling/hwrepo/pcb_drc_exclusion_native.py#source_bound_pcb_drc_exclusion_matches"
        in rule["implementation_refs"]
    )
