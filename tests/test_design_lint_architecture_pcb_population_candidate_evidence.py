"""Guard typed source ownership for PCB DNP population findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_population_candidate_evidence import (
    PcbBlockedVariantPopulationCandidate,
    PcbPopulationCandidate,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventorySourceReceipt,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_population_findings_use_typed_source_owners_for_each_evidence_state() -> None:
    owner_path = HWREPO / "design_lint_pcb_population_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_component_inventory_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbPopulationCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_population_candidate_evidence"
    )
    assert PcbBlockedVariantPopulationCandidate.__module__ == PcbPopulationCandidate.__module__
    assert PcbComponentInventorySourceReceipt.__module__ == (
        "kicad_tooling.hwrepo.pcb_component_inventory_models"
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    for name in (
        "project_pcb_population_evidence",
        "project_blocked_variant_population_evidence",
    ):
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == name for node in owner_tree.body
        )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_component_inventory_candidates"
    )
    source_owners = [
        owner
        for node in ast.walk(translator_function)
        if (owner := _source_evidence_owner(node)) is not None
    ]
    assert len(source_owners) == 4
    assert set(source_owners) == {
        "PcbInventoryCandidate",
        "PcbPopulationCandidate",
        "PcbBlockedVariantPopulationCandidate",
    }
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "project_named_variant_population_evidence"
        for node in ast.walk(translator_function)
    )


def _source_evidence_owner(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr != "from_source_evidence" or not isinstance(node.func.value, ast.Name):
        return None
    return node.func.value.id
