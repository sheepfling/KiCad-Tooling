"""Guard connector open-pin evidence ownership and source routing."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_connector_pin_candidates,
    design_lint_connector_unconnected_pin_candidate_evidence,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]


def test_connector_open_pin_projector_has_one_focused_owner() -> None:
    owner_path = HWREPO / "design_lint_connector_unconnected_pin_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_unconnected_connector_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )
    assert (
        design_lint_connector_pin_candidates.UnconnectedConnectorPinCandidate
        is design_lint_connector_unconnected_pin_candidate_evidence.UnconnectedConnectorPinCandidate
    )


def test_all_four_unconnected_connector_rules_retain_their_scan_record() -> None:
    service_path = HWREPO / "design_lint_connector_pin_candidates.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=service_path.name)
    candidate_builder = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "connector_pin_candidates"
    )
    source_loops = {
        node.iter.id: node
        for node in ast.walk(candidate_builder)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name)
        and node.iter.id
        in {
            "unconnected_power_input_pins",
            "unconnected_power_output_pins",
            "unconnected_named_pins",
        }
    }

    assert set(source_loops) == {
        "unconnected_power_input_pins",
        "unconnected_power_output_pins",
        "unconnected_named_pins",
    }
    for loop in source_loops.values():
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(loop)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        )
