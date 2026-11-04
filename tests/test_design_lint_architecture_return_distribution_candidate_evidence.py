"""Guard evidence ownership for authored connector return distribution."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.evidence_lint,
]


def test_return_distribution_projection_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_return_distribution_candidate_evidence.py"
    adapter = HWREPO / "design_lint_return_distribution_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_return_distribution_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "ConnectorReturnDistributionCandidate"
        for node in owner_tree.body
    )


def test_candidate_adapter_routes_each_open_entry_without_inline_evidence() -> None:
    path = HWREPO / "design_lint_return_distribution_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "return_distribution_candidates"
    )
    loops = [node for node in ast.walk(adapter) if isinstance(node, ast.For)]

    assert len(loops) == 1
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(loops[0])
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(adapter)
    )
