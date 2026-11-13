"""Keep the unassigned copper pad heuristic in a focused PCB owner."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.catalog_lint,
    pytest.mark.rule_gate_integrity,
]

ROOT = Path(__file__).resolve().parents[1]
OWNER = "kicad_tooling/hwrepo/pcb_unassigned_copper_pad.py#unassigned_copper_pad_candidates"
RULE_ID = "pcb.unassigned_copper_pad_review"


def test_rule_owner_is_a_bounded_pcb_source_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_name = OWNER.split("#", maxsplit=1)
    owner = ROOT / owner_path
    source = owner.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=owner.name)
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert rule.theme == "pcb"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert owner_name in functions
    assert len(source.splitlines()) < 500
    assert "pcb_unassigned_copper_pad" not in (
        ROOT / "kicad_tooling/hwrepo/design_lint.py"
    ).read_text(encoding="utf-8")


def test_project_inspection_dispatches_the_source_candidate_from_its_owner() -> None:
    source = (ROOT / "kicad_tooling/hwrepo/design_lint_project_inspection.py").read_text(
        encoding="utf-8"
    )

    assert "from .pcb_unassigned_copper_pad import unassigned_copper_pad_candidates" in source
    assert "*unassigned_copper_pad_candidates(" in source
