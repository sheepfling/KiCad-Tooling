"""Guard I2C pull-up candidate ownership and its compatibility facade."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_bus_heuristics_compatibility_facade_stays_small() -> None:
    assert line_count(HWREPO / "bus_heuristics.py") < FACADE_MAX_LINES


def test_i2c_candidate_scan_delegates_wire_projection_to_the_theme_owner() -> None:
    adapter = HWREPO / "i2c_pullup_compatibility.py"
    evidence_owner = HWREPO / "design_lint_i2c_pullup_candidate_evidence.py"
    candidate_source = HWREPO / "design_lint_i2c_pullup_candidates.py"
    candidate_tree = ast.parse(candidate_source.read_text(encoding="utf-8"))
    imports = {node.module for node in candidate_tree.body if isinstance(node, ast.ImportFrom)}

    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence_owner) < IMPLEMENTATION_MAX_LINES
    assert "i2c_pullup_heuristics" in imports
    assert "design_lint_i2c_pullup_candidate_evidence" in imports
    assert "i2c_pullup_compatibility" not in imports
    assert "bus_heuristics" not in imports
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence"
        for node in ast.walk(candidate_tree)
    )
