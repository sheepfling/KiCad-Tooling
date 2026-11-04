"""Guard the typed candidate source path for CAN termination findings."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_can_termination_candidates_use_the_theme_evidence_owner() -> None:
    evidence_owner = HWREPO / "design_lint_can_termination_candidate_evidence.py"
    candidate_source = HWREPO / "design_lint_can_candidates.py"
    tree = ast.parse(candidate_source.read_text(encoding="utf-8"))
    imports = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    coordinator = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "can_candidates"
    )
    direct_candidate_rules = {
        keyword.value.value
        for call in ast.walk(coordinator)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "Candidate"
        for keyword in call.keywords
        if keyword.arg == "rule_id"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }

    assert line_count(evidence_owner) < IMPLEMENTATION_MAX_LINES
    assert "design_lint_can_termination_candidate_evidence" in imports
    assert "bus.can_missing_termination" not in direct_candidate_rules
    assert "bus.can_excess_termination" not in direct_candidate_rules
