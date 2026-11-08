"""Keep alternate reference-plane review policy and predicate ownership explicit."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]

RULE_ID = "pcb.alternate_reference_plane_run"
OWNER = (
    "kicad_tooling/hwrepo/pcb_reference_plane_transitions.py#"
    "alternate_reference_plane_run_candidates"
)


def test_rule_is_opt_in_review_owned_by_the_focused_predicate_module() -> None:
    catalog_path = REPO_ROOT / "kicad_tooling/hwrepo/design-lint-rules.json"
    rules = json.loads(catalog_path.read_text(encoding="utf-8"))["rules"]
    rule = next(item for item in rules if item["rule_id"] == RULE_ID)
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/pcb_reference_plane_transitions.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    functions = {node.name for node in owner_tree.body if isinstance(node, ast.FunctionDef)}

    assert rule["status"] == "active"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == OWNER
    assert OWNER in rule["implementation_refs"]
    assert "alternate_reference_plane_run_candidates" in functions
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert "pcb.alternate_reference_plane_run" in ast.unparse(owner_tree)


def test_catalog_names_the_project_threshold_and_noncontinuity_limit() -> None:
    rules = json.loads(
        (REPO_ROOT / "kicad_tooling/hwrepo/design-lint-rules.json").read_text(encoding="utf-8")
    )["rules"]
    rule = next(item for item in rules if item["rule_id"] == RULE_ID)

    assert "minimum_alternate_reference_length_um" in rule["predicate"]
    assert any("disjoint" in item for item in rule["limitations"])
    assert rule["required_native_fixtures"] == ["KICAD_RUN_NATIVE_PCB_FIXTURES"]
