"""Guard typed ownership of blocked PCB inventory candidates."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_blocked_inventory_evidence import (
    PcbBlockedComponentInventoryCandidate,
    PcbBlockedPopulationCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_blocked_inventory_findings_use_a_typed_source_owner() -> None:
    owner_path = HWREPO / "design_lint_pcb_blocked_inventory_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_component_inventory_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbBlockedComponentInventoryCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_blocked_inventory_evidence"
    )
    assert (
        PcbBlockedPopulationCandidate.__module__ == PcbBlockedComponentInventoryCandidate.__module__
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    for name in (
        "project_blocked_component_inventory_evidence",
        "project_blocked_population_evidence",
    ):
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == name for node in owner_tree.body
        )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_component_inventory_candidates"
    )
    owner_calls = {
        node.func.value.id
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id
        in {"PcbBlockedComponentInventoryCandidate", "PcbBlockedPopulationCandidate"}
    }
    assert owner_calls == {
        "PcbBlockedComponentInventoryCandidate",
        "PcbBlockedPopulationCandidate",
    }

    opaque_blocked_candidates = [
        node
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        and any(
            keyword.arg == "rule_id"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value
            in {"pcb.schematic_component_inventory", "pcb.schematic_pcb_dnp_mismatch"}
            for keyword in node.keywords
        )
    ]
    assert opaque_blocked_candidates == []
