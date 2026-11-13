"""Guard source ownership and size for the custom DRC disallow-object lint."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES
from tests.lint_architecture_support import line_count as _line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture, pytest.mark.pcb_lint]


def test_unknown_disallow_object_predicate_has_focused_typed_owners() -> None:
    modules = (
        "pcb_drc_rule_parser.py",
        "pcb_drc_rule_structure.py",
        "pcb_dru_constraint_type_registry.py",
        "design_lint_pcb_dru_unknown_disallowed_object_evidence.py",
        "pcb_dru_unknown_disallowed_object_review.py",
    )
    sizes = {name: _line_count(HWREPO / name) for name in modules}
    assert all(lines < IMPLEMENTATION_MAX_LINES for lines in sizes.values()), sizes

    owner_path = HWREPO / "pcb_dru_unknown_disallowed_object_review.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    owner_functions = {node.name for node in owner_tree.body if isinstance(node, ast.FunctionDef)}
    assert "unknown_custom_drc_disallowed_object_candidates" in owner_functions

    collector = HWREPO / "design_lint_pcb_dru_candidates.py"
    collector_tree = ast.parse(collector.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pcb_dru_unknown_disallowed_object_review"
        and any(
            alias.name == "unknown_custom_drc_disallowed_object_candidates" for alias in node.names
        )
        for node in collector_tree.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "unknown_custom_drc_disallowed_object_candidates"
        for node in ast.walk(collector_tree)
    )

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item
        for item in catalog["rules"]
        if item["rule_id"] == "pcb.custom_drc_unknown_disallowed_object_type"
    )
    assert rule["implementation_owner"] == (
        "kicad_tooling/hwrepo/pcb_dru_unknown_disallowed_object_review.py#"
        "unknown_custom_drc_disallowed_object_candidates"
    )
    assert (
        "kicad_tooling/hwrepo/pcb_drc_rule_structure.py#native_rule_declarations"
        in rule["implementation_refs"]
    )
