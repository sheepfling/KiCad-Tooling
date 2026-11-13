"""Guard focused ownership for exact-net custom DRC scope review."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.drc_exact_net_scope_unmatched"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_exact_net_scope_uses_shared_inventory_parser_and_focused_scan() -> None:
    modules = (
        "pcb_board_net_inventory.py",
        "pcb_drc_netclass_patterns.py",
        "pcb_drc_exact_net_scope.py",
        "pcb_drc_exact_net_scope_scan.py",
    )
    assert all(
        len((HWREPO / name).read_text(encoding="utf-8").splitlines()) < 500 for name in modules
    )
    netclass = ast.parse((HWREPO / "pcb_drc_netclass_patterns.py").read_text(encoding="utf-8"))
    assert any(
        node.module == "pcb_board_net_inventory"
        and any(alias.name == "pcb_board_net_names" for alias in node.names)
        for node in netclass.body
        if isinstance(node, ast.ImportFrom)
    )

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner = "kicad_tooling/hwrepo/pcb_drc_exact_net_scope.py#unmatched_exact_net_scope_candidates"
    scan = (
        "kicad_tooling/hwrepo/pcb_drc_exact_net_scope_scan.py#scan_unmatched_exact_net_drc_scopes"
    )
    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == owner
    assert owner in rule["implementation_refs"]
    assert scan in rule["implementation_refs"]
    assert (
        "kicad_tooling/hwrepo/pcb_board_net_inventory.py#pcb_board_net_names"
        in rule["implementation_refs"]
    )
    assert (
        "kicad_tooling/hwrepo/pcb_drc_conditions.py#native_exact_net_condition"
        in rule["implementation_refs"]
    )

    inspection = ast.parse((HWREPO / "design_lint_project_inspection.py").read_text())
    assert any(
        node.module == "pcb_drc_exact_net_scope_scan"
        and any(alias.name == "scan_unmatched_exact_net_drc_scopes" for alias in node.names)
        for node in inspection.body
        if isinstance(node, ast.ImportFrom)
    )
    assert RULE_ID in (HWREPO / "design_lint_rule_types.py").read_text(encoding="utf-8")
