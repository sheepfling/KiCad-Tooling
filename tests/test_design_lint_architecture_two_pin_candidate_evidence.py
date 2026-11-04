"""Guard the typed source owner for same-net two-pin candidates."""

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


def test_two_pin_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_two_pin_candidate_evidence.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_two_pin_component_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "TwoPinSameNetCandidate"
        for node in owner_tree.body
    )


def test_two_pin_adapter_routes_through_the_typed_projection_owner() -> None:
    path = HWREPO / "design_lint_component_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "TwoPinSameNetCandidate"
        and node.func.attr == "from_source_evidence"
    ]

    assert len(calls) == 1
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(calls[0])
    )
