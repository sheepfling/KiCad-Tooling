"""Guard ownership and source boundaries for exact DRC reference scopes."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.drc_exact_reference_scope_unmatched"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_exact_reference_scope_has_focused_inventory_predicate_and_scan() -> None:
    modules = (
        "pcb_drc_conditions.py",
        "pcb_drc_exact_reference_scope.py",
        "pcb_drc_exact_reference_scope_scan.py",
        "pcb_footprint_reference_inventory.py",
    )
    assert all(
        len((HWREPO / name).read_text(encoding="utf-8").splitlines()) < 500 for name in modules
    )

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner = (
        "kicad_tooling/hwrepo/pcb_drc_exact_reference_scope.py"
        "#unmatched_exact_reference_scope_candidates"
    )
    scan = (
        "kicad_tooling/hwrepo/pcb_drc_exact_reference_scope_scan.py"
        "#scan_unmatched_exact_reference_drc_scopes"
    )
    inventory = (
        "kicad_tooling/hwrepo/pcb_footprint_reference_inventory.py"
        "#pcb_board_footprint_reference_names"
    )
    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == owner
    assert {owner, scan, inventory} <= set(rule["implementation_refs"])

    collector = ast.parse((HWREPO / "design_lint_pcb_dru_candidates.py").read_text())
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scan_unmatched_exact_reference_drc_scopes"
        for function in collector.body
        if isinstance(function, ast.FunctionDef) and function.name == "collect_pcb_dru_candidates"
        for node in ast.walk(function)
    )
    scan_module = ast.parse((HWREPO / "pcb_drc_exact_reference_scope_scan.py").read_text())
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "verify_source_bound_drc_unchanged"
        for node in ast.walk(scan_module)
    )
    for parser_name in ("pcb_pad_source.py", "pcb_footprint_path_integrity.py"):
        parser = ast.parse((HWREPO / parser_name).read_text(encoding="utf-8"))
        assert any(
            node.module == "pcb_footprint_reference_inventory"
            and any(alias.name == "pcb_footprint_reference" for alias in node.names)
            for node in parser.body
            if isinstance(node, ast.ImportFrom)
        )
    assert RULE_ID in (HWREPO / "design_lint_rule_types.py").read_text(encoding="utf-8")
