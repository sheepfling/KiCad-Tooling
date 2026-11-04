"""Guard the typed source route for PCB footprint inventory findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_inventory_candidate_evidence import (
    PcbInventoryCandidate,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventorySourceReceipt,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_inventory_candidate_translation_uses_one_typed_source_owner() -> None:
    owner_path = HWREPO / "design_lint_pcb_inventory_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_component_inventory_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbInventoryCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_inventory_candidate_evidence"
    )
    assert PcbComponentInventorySourceReceipt.__module__ == (
        "kicad_tooling.hwrepo.pcb_component_inventory_models"
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_pcb_inventory_evidence"
        for node in owner_tree.body
    )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_component_inventory_candidates"
    )
    typed_calls = [
        node for node in ast.walk(translator_function) if _is_inventory_candidate_call(node)
    ]
    assert len(typed_calls) == 2


def _is_inventory_candidate_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if not isinstance(node.func.value, ast.Name):
        return False
    return (
        node.func.attr == "from_source_evidence" and node.func.value.id == "PcbInventoryCandidate"
    )
