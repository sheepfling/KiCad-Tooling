"""Keep PCB footprint path identity review bounded and source-bound."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]

ROOT = Path(__file__).resolve().parents[1]
RULE_ID = "pcb.footprint_path_trailing_separator"
OWNER = (
    "kicad_tooling/hwrepo/pcb_footprint_path_integrity.py#"
    "pcb_footprint_path_trailing_separator_candidates"
)


def test_rule_owner_is_a_bounded_pcb_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_name = OWNER.split("#", maxsplit=1)
    owner = ROOT / owner_path
    tree = ast.parse(owner.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert rule.theme == "pcb"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert owner_name in functions
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500


def test_footprint_path_and_duplicate_uuid_checks_share_board_binding() -> None:
    path_owner = ROOT / "kicad_tooling/hwrepo/pcb_footprint_path_integrity.py"
    uuid_owner = ROOT / "kicad_tooling/hwrepo/pcb_object_uuid_integrity.py"
    binding_owner = ROOT / "kicad_tooling/hwrepo/pcb_board_source_binding.py"
    identity_owner = ROOT / "kicad_tooling/hwrepo/pcb_source_identity.py"
    inspection = ROOT / "kicad_tooling/hwrepo/design_lint_project_inspection.py"
    paths = (path_owner, uuid_owner, binding_owner, identity_owner)
    oversized = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in paths}
    path_source = path_owner.read_text(encoding="utf-8")
    uuid_source = uuid_owner.read_text(encoding="utf-8")
    inspection_source = inspection.read_text(encoding="utf-8")

    assert all(lines < 500 for lines in oversized.values()), oversized
    assert "read_source_bound_pcb_board" in path_source
    assert "read_source_bound_pcb_board" in uuid_source
    assert "canonical_pcb_uuid" in path_source
    assert "canonical_pcb_uuid" in uuid_source
    assert "pcb_footprint_path_trailing_separator_candidates" in inspection_source
