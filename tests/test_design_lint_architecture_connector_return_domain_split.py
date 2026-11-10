"""Guard the mapped return-domain predicate and its typed evidence boundary."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]


def test_return_domain_split_owner_and_evidence_modules_stay_focused() -> None:
    owner = HWREPO / "design_lint_connectors_return_domains.py"
    evidence = HWREPO / "design_lint_return_domain_split_candidate_evidence.py"

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence) < IMPLEMENTATION_MAX_LINES


def test_return_domain_split_predicate_constructs_typed_source_evidence() -> None:
    path = HWREPO / "design_lint_connectors_return_domains.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "mapped_same_domain_return_split_net_candidates"
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "MappedReturnDomainSplitCandidate"
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(function)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    )


def test_return_domain_candidate_reprojects_only_current_mapped_pins() -> None:
    path = HWREPO / "design_lint_return_domain_split_candidate_evidence.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)

    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_mapped_return_domain_split_evidence"
        for node in tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "MappedReturnDomainSplitFindingEvidence"
        for node in tree.body
    )
