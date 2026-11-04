"""Guard the I2C address candidate source-evidence owner."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_i2c_address_candidates_delegate_wire_evidence_to_the_theme_owner() -> None:
    evidence_owner = HWREPO / "design_lint_i2c_address_candidate_evidence.py"
    candidate_source = HWREPO / "design_lint_i2c_candidates.py"
    tree = ast.parse(candidate_source.read_text(encoding="utf-8"))
    imports = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    address_functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"i2c_address_candidates", "i2c_responder_coverage_candidates"}
    }

    assert line_count(evidence_owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(candidate_source) < IMPLEMENTATION_MAX_LINES
    assert "design_lint_i2c_address_candidate_evidence" in imports
    assert set(address_functions) == {
        "i2c_address_candidates",
        "i2c_responder_coverage_candidates",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for function in address_functions.values()
        for node in ast.walk(function)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence"
        for function in address_functions.values()
        for node in ast.walk(function)
    )
