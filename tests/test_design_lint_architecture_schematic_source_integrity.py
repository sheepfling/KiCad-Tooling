"""Keep source-integrity ownership inside a small schematic theme module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

RULE_ID = "schematic.missing_embedded_symbol_definition"
OWNER = (
    "kicad_tooling/hwrepo/schematic_source_integrity.py#missing_embedded_library_symbol_candidates"
)
pytestmark = [pytest.mark.design_lint, pytest.mark.schematic_lint, pytest.mark.architecture]


def test_missing_embedded_symbol_predicate_has_a_small_schematic_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_function = rule.implementation_owner.split("#", 1)
    module = HWREPO / "schematic_source_integrity.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    functions = {item.name for item in tree.body if isinstance(item, ast.FunctionDef)}

    assert rule.implementation_owner == OWNER
    assert rule.implementation_owner in rule.implementation_refs
    assert owner_path.startswith("kicad_tooling/hwrepo/schematic_")
    assert owner_function in functions
    assert module.is_file()
    assert line_count(module) < IMPLEMENTATION_MAX_LINES
    assert "schematic_source_integrity.py#" not in (HWREPO / "design_lint.py").read_text(
        encoding="utf-8"
    )
