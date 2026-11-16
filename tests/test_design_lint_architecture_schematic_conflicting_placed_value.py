"""Keep the duplicate placed-value predicate in its schematic owner."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

RULE_ID = "schematic.conflicting_placed_value_properties"
OWNER = (
    "kicad_tooling/hwrepo/schematic_conflicting_placed_value.py#"
    "source_bound_conflicting_placed_value_candidates"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]


def test_conflicting_placed_value_predicate_has_a_small_schematic_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_function = rule.implementation_owner.split("#", 1)
    module = HWREPO / "schematic_conflicting_placed_value.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    functions = {item.name for item in tree.body if isinstance(item, ast.FunctionDef)}

    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert owner_path.startswith("kicad_tooling/hwrepo/schematic_")
    assert owner_function in functions
    assert module.is_file()
    assert line_count(module) < IMPLEMENTATION_MAX_LINES
