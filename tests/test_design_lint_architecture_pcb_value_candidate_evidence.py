"""Guard typed source ownership for PCB component-value findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_value_candidate_evidence import (
    PcbBlockedValueComparisonCandidate,
    PcbValueMismatchCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_value_findings_use_typed_source_and_blocked_coverage_owners() -> None:
    owner_path = HWREPO / "design_lint_pcb_value_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    variant_owner_path = HWREPO / "design_lint_pcb_variant_population_evidence.py"
    variant_owner_tree = ast.parse(variant_owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_component_inventory_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbValueMismatchCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_value_candidate_evidence"
    )
    assert PcbBlockedValueComparisonCandidate.__module__ == PcbValueMismatchCandidate.__module__
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(variant_owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_named_variant_population_evidence"
        for node in variant_owner_tree.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "project_named_variant_population_evidence"
        for node in ast.walk(owner_tree)
    )
    for name in (
        "project_pcb_value_mismatch_evidence",
        "project_blocked_value_comparison_evidence",
    ):
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == name for node in owner_tree.body
        )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_component_inventory_candidates"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "PcbValueMismatchCandidate"
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(translator_function)
    )
    assert (
        sum(
            1
            for node in ast.walk(translator_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_blocked_value_candidate"
        )
        == 2
    )


def test_value_report_translation_does_not_construct_opaque_candidates() -> None:
    translator_path = HWREPO / "design_lint_pcb_component_inventory_candidates.py"
    tree = ast.parse(translator_path.read_text(encoding="utf-8"))
    value_rule_candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        and any(
            keyword.arg == "rule_id"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "pcb.schematic_pcb_value_mismatch"
            for keyword in node.keywords
        )
    ]

    assert value_rule_candidates == []
