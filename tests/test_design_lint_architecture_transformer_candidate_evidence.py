"""Guard the named transformer source records and candidate projection owner."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def test_transformer_source_and_evidence_owners_stay_focused() -> None:
    model = HWREPO / "design_lint_component_transformer_models.py"
    evidence = HWREPO / "design_lint_component_transformer_candidate_evidence.py"

    assert line_count(model) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence) < IMPLEMENTATION_MAX_LINES
    model_tree = ast.parse(model.read_text(encoding="utf-8"), filename=model.name)
    evidence_tree = ast.parse(evidence.read_text(encoding="utf-8"), filename=evidence.name)
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "TransformerWindingPinGroup"
        for node in model_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "TransformerPinNetAssignment"
        for node in model_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_transformer_evidence"
        for node in evidence_tree.body
    )


def test_transformer_predicates_route_through_source_bound_candidates() -> None:
    path = HWREPO / "design_lint_component_transformers.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "transformer_winding_same_net_candidates",
            "transformer_winding_groups_share_net_candidates",
        }
    }

    assert len(functions) == 2
    for function in functions.values():
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "TransformerCandidate"
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(function)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        )
