"""Guard the typed source owner for I2C peer-reference candidates."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.evidence_lint,
]


def test_i2c_peer_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_i2c_peer_candidate_evidence.py"
    adapter = HWREPO / "design_lint_i2c_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_i2c_peer_reference_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "I2cPeerReferenceCandidate"
        for node in owner_tree.body
    )


def test_i2c_peer_adapter_uses_the_typed_projection_owner() -> None:
    path = HWREPO / "design_lint_i2c_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "i2c_peer_reference_candidates"
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "I2cPeerReferenceCandidate"
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(function)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "I2cPeerReferenceFindingEvidence"
        for node in ast.walk(function)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    )
