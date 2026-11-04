"""Guard LED topology candidate evidence ownership."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_component_candidates,
    design_lint_led_candidate_evidence,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def test_led_candidate_evidence_has_one_focused_component_owner() -> None:
    owner_path = HWREPO / "design_lint_led_candidate_evidence.py"
    service_path = HWREPO / "design_lint_component_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(service_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_led_candidate_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )
    assert (
        design_lint_component_candidates.LedTopologyCandidate
        is design_lint_led_candidate_evidence.LedTopologyCandidate
    )


def test_both_led_scan_paths_retain_typed_source_without_inline_evidence() -> None:
    service_path = HWREPO / "design_lint_component_candidates.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=service_path.name)
    scanner_names = {
        "leds_directly_between_positive_and_return_nets",
        "leds_directly_driven_without_visible_series_resistor",
    }
    scanner_loops = [
        node
        for node in ast.walk(service_tree)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id in scanner_names
    ]

    assert {loop.iter.func.id for loop in scanner_loops if isinstance(loop.iter, ast.Call)} == (
        scanner_names
    )
    for loop in scanner_loops:
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        )
