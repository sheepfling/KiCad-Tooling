"""Guard the typed evidence route for power and supply candidate sources."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]

_SOURCE_LOOPS = {
    "same_voltage_power_inputs_on_different_nets",
    "ic_power_rails_without_fitted_capacitors",
    "power_inputs_without_supported_source_paths",
    "connector_capacitor_only_nets",
    "component_supply_pins_on_different_nets",
    "numbered_power_rail_groups",
}


def test_power_source_projections_have_a_small_typed_owner() -> None:
    owner = HWREPO / "design_lint_power_candidate_evidence.py"
    adapter = HWREPO / "design_lint_power_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_power_candidate_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "PowerCandidate" for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )


def test_each_power_source_loop_uses_the_typed_projection_adapter() -> None:
    path = HWREPO / "design_lint_power_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    scan = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "scan_power_candidates"
    )
    loops = {
        node.iter.func.id: node
        for node in ast.walk(scan)
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
