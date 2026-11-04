"""Guard the shared named-variant PCB source-evidence projection."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_variant_population_evidence import (
    project_named_variant_population_evidence,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_named_variant_projection_has_one_source_owner_and_two_theme_consumers() -> None:
    owner_path = HWREPO / "design_lint_pcb_variant_population_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))

    assert project_named_variant_population_evidence.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_variant_population_evidence"
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    owner_function = next(
        node
        for node in owner_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "project_named_variant_population_evidence"
    )
    assert isinstance(owner_function.returns, ast.Name)
    assert owner_function.returns.id == "CandidateEvidenceProjection"
    assert any(
        isinstance(node, ast.Name) and node.id == "PcbVariantPopulationCoverage"
        for node in ast.walk(owner_function)
    )

    for filename, expected_rule in (
        ("design_lint_pcb_population_candidate_evidence.py", "pcb.schematic_pcb_dnp_mismatch"),
        ("design_lint_pcb_value_candidate_evidence.py", "pcb.schematic_pcb_value_mismatch"),
    ):
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "project_named_variant_population_evidence"
        ]
        assert len(calls) == 1, filename
        rule_ids = {
            keyword.value.value
            for node in calls
            for keyword in node.keywords
            if keyword.arg == "rule_id" and isinstance(keyword.value, ast.Constant)
        }
        assert rule_ids == {expected_rule}, filename
