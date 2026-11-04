"""Guard typed connector peer-pin candidate evidence ownership."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    connector_peer_candidate_evidence,
    design_lint_connector_pin_candidates,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]


def test_repeated_and_generic_peer_findings_have_one_connector_evidence_owner() -> None:
    owner_path = HWREPO / "connector_peer_candidate_evidence.py"
    service_path = HWREPO / "design_lint_connector_pin_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_repeated_connector_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_connector_peer_pin_assignment_evidence"
        for node in owner_tree.body
    )
    assert (
        design_lint_connector_pin_candidates.RepeatedConnectorPinCandidate
        is connector_peer_candidate_evidence.RepeatedConnectorPinCandidate
    )
    assert (
        design_lint_connector_pin_candidates.ConnectorPeerPinAssignmentCandidate
        is connector_peer_candidate_evidence.ConnectorPeerPinAssignmentCandidate
    )

    service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=service_path.name)
    builder = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "connector_pin_candidates"
    )
    routed_loops = [
        node
        for node in ast.walk(builder)
        if isinstance(node, ast.For)
        and (
            isinstance(node.iter, ast.Name)
            and node.iter.id == "repeated_connector_pin_groups"
            or isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id
            in {
                "connector_peer_pin_assignment_outliers",
                "connector_peer_pin_assignment_divergences",
            }
        )
    ]

    assert len(routed_loops) == 3
    for loop in routed_loops:
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(builder)
    )
