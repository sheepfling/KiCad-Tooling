"""Keep source-integrity ownership inside a small schematic theme module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

RULE_OWNERS = {
    "schematic.missing_embedded_symbol_definition": (
        "kicad_tooling/hwrepo/schematic_source_integrity.py#missing_embedded_library_symbol_candidates"
    ),
    "schematic.duplicate_embedded_symbol_definition": (
        "kicad_tooling/hwrepo/schematic_source_integrity.py#duplicate_embedded_library_symbol_candidates"
    ),
    "schematic.embedded_symbol_pin_number_mismatch": (
        "kicad_tooling/hwrepo/schematic_source_integrity.py#embedded_symbol_pin_number_mismatch_candidates"
    ),
    "schematic.duplicate_object_uuid": (
        "kicad_tooling/hwrepo/schematic_source_integrity.py#duplicate_schematic_object_uuid_candidates"
    ),
}
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]


@pytest.mark.parametrize(("rule_id", "owner"), RULE_OWNERS.items())
def test_embedded_symbol_predicates_have_small_schematic_owners(rule_id: str, owner: str) -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == rule_id)
    owner_path, owner_function = rule.implementation_owner.split("#", 1)
    module = HWREPO / "schematic_source_integrity.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    functions = {item.name for item in tree.body if isinstance(item, ast.FunctionDef)}

    assert rule.implementation_owner == owner
    assert rule.implementation_owner in rule.implementation_refs
    assert owner_path.startswith("kicad_tooling/hwrepo/schematic_")
    assert owner_function in functions
    assert module.is_file()
    assert line_count(module) < IMPLEMENTATION_MAX_LINES
    assert "schematic_source_integrity.py#" not in (HWREPO / "design_lint.py").read_text(
        encoding="utf-8"
    )
