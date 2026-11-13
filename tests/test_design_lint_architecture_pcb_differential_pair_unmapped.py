"""Guard ownership and module boundaries for unmapped pair-selector review."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.differential_pair_unmapped_native_rule"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unmapped_pair_rule_uses_focused_predicate_and_source_scan() -> None:
    modules = (
        "pcb_drc_conditions.py",
        "pcb_differential_pair_unmapped.py",
        "pcb_differential_pair_unmapped_scan.py",
    )
    assert all(
        len((HWREPO / name).read_text(encoding="utf-8").splitlines()) < 500 for name in modules
    )

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner = (
        "kicad_tooling/hwrepo/pcb_differential_pair_unmapped.py#"
        "unmapped_differential_pair_rule_candidates"
    )
    scan = (
        "kicad_tooling/hwrepo/pcb_differential_pair_unmapped_scan.py#"
        "scan_unmapped_differential_pair_rules"
    )
    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == owner
    assert owner in rule["implementation_refs"]
    assert scan in rule["implementation_refs"]
    assert ("kicad_tooling/hwrepo/pcb_drc_conditions.py#native_exact_diff_pair_condition") in rule[
        "implementation_refs"
    ]

    inspection = ast.parse((HWREPO / "design_lint_project_inspection.py").read_text())
    assert any(
        node.module == "pcb_differential_pair_unmapped_scan"
        and any(alias.name == "scan_unmapped_differential_pair_rules" for alias in node.names)
        for node in inspection.body
        if isinstance(node, ast.ImportFrom)
    )
    assert RULE_ID in (HWREPO / "design_lint_rule_types.py").read_text(encoding="utf-8")
