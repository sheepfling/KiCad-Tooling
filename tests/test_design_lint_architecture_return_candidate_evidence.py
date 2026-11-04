"""Guard typed evidence ownership for connector and return-domain candidates."""

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

_SOURCE_LOOPS = {
    "connectors_without_connected_return",
    "return_net_groups",
    "return_label_groups_without_pin_roles",
}


def test_return_domain_projector_has_a_small_theme_owner() -> None:
    owner = HWREPO / "design_lint_return_candidate_evidence.py"
    adapter = HWREPO / "design_lint_return_domain_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_return_candidate_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "ReturnDomainCandidate"
        for node in owner_tree.body
    )


def test_each_return_scan_loop_uses_its_typed_source_variant() -> None:
    path = HWREPO / "design_lint_return_domain_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "return_domain_candidates"
    )
    loops = {
        node.iter.func.id: node
        for node in ast.walk(adapter)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
    }

    assert _SOURCE_LOOPS <= loops.keys()
    for source_name in _SOURCE_LOOPS:
        loop = loops[source_name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        ), source_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        ), source_name
