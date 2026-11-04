"""Guard the typed candidate route shared by BJT and MOSFET terminal rules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_component_terminal_candidate_evidence import (
    ComponentTerminalCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.component_lint]

_PREDICATES = {
    "design_lint_component_bjt_terminals.py": (
        "bjts_with_collector_emitter_on_same_net",
        "bjts_with_base_emitter_on_same_net",
        "bjts_with_base_collector_on_same_net",
    ),
    "design_lint_component_mosfet_terminals.py": (
        "mosfets_with_drain_source_on_same_net",
        "mosfets_with_gate_source_on_same_net",
        "mosfets_with_gate_drain_on_same_net",
    ),
}


def test_supported_terminal_predicates_use_one_component_evidence_owner() -> None:
    owner_path = HWREPO / "design_lint_component_terminal_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))

    assert ComponentTerminalCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_component_terminal_candidate_evidence"
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_component_terminal_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )

    for filename, function_names in _PREDICATES.items():
        predicate_path = HWREPO / filename
        tree = ast.parse(predicate_path.read_text(encoding="utf-8"))
        assert line_count(predicate_path) < IMPLEMENTATION_MAX_LINES
        for function_name in function_names:
            function = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == function_name
            )
            assert any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "from_source_evidence"
                for node in ast.walk(function)
            ), function_name
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Candidate"
                for node in ast.walk(function)
            ), function_name
