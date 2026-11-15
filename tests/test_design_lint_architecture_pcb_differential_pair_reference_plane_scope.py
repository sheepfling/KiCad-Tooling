"""Guard owner, scope, and module size for pair-plane coverage review."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.architecture,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_reference_plane_scope_missing"),
]

RULE_ID = "pcb.differential_pair_reference_plane_scope_missing"
OWNER = (
    "kicad_tooling/hwrepo/pcb_pair_reference_plane_scope.py#"
    "pcb_differential_pair_reference_plane_scope_candidates"
)


def test_rule_uses_small_pcb_owned_map_coverage_predicate() -> None:
    catalog = json.loads(
        (REPO_ROOT / "kicad_tooling/hwrepo/design-lint-rules.json").read_text(encoding="utf-8")
    )
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    source_path = REPO_ROOT / "kicad_tooling/hwrepo/pcb_pair_reference_plane_scope.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert rule["status"] == "active"
    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "review"
    assert rule["implementation_owner"] == OWNER
    assert OWNER in rule["implementation_refs"]
    assert "pcb_reference_plane_map.signal_net" in rule["predicate"]
    assert rule["required_native_fixtures"] == []
    assert "does not require a shared ground/reference net" in rule["limitations"][1]
    assert "pcb_differential_pair_reference_plane_scope_candidates" in functions
    assert line_count(source_path) < IMPLEMENTATION_MAX_LINES


def test_candidate_test_module_stays_within_review_limit() -> None:
    test_path = REPO_ROOT / "tests/test_pcb_differential_pair_reference_plane_scope.py"
    assert line_count(test_path) < IMPLEMENTATION_MAX_LINES
