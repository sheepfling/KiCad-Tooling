"""Guard the unconnected component-pin evidence ownership boundary."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    component_power_output_candidates,
    design_lint_component_candidates,
    design_lint_component_unconnected_pin_candidate_evidence,
    design_lint_power_candidates,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def test_component_pin_evidence_has_a_focused_owner() -> None:
    owner_path = HWREPO / "design_lint_component_unconnected_pin_candidate_evidence.py"
    service_path = HWREPO / "design_lint_component_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(service_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_unconnected_component_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )
    assert (
        design_lint_component_candidates.UnconnectedComponentPinCandidate
        is design_lint_component_unconnected_pin_candidate_evidence.UnconnectedComponentPinCandidate
    )


def test_named_component_pin_adapter_routes_the_scan_record_without_inline_evidence() -> None:
    service_path = HWREPO / "design_lint_component_candidates.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=service_path.name)
    adapter = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_unconnected_named_pin_candidate"
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(adapter)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(adapter)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(adapter)
    )


def test_generic_component_power_pins_use_the_same_typed_evidence_owner() -> None:
    power_path = HWREPO / "design_lint_power_candidates.py"
    output_path = HWREPO / "component_power_output_candidates.py"
    power_tree = ast.parse(power_path.read_text(encoding="utf-8"), filename=power_path.name)
    output_tree = ast.parse(output_path.read_text(encoding="utf-8"), filename=output_path.name)
    power_scan = next(
        node
        for node in power_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "scan_power_candidates"
    )
    input_loop = next(
        node
        for node in ast.walk(power_scan)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "unconnected_generic_power_input_component_pins"
    )
    output_adapter = next(
        node
        for node in output_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "unconnected_power_output_candidates"
    )

    assert all(line_count(path) < IMPLEMENTATION_MAX_LINES for path in (power_path, output_path))
    for filename, tree in ((power_path.name, power_tree), (output_path.name, output_tree)):
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "design_lint_component_unconnected_pin_candidate_evidence"
            and "UnconnectedComponentPinCandidate" in {alias.name for alias in node.names}
            for node in tree.body
        ), filename
    for adapter in (input_loop, output_adapter):
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(adapter)
        )
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(adapter)
        )
    assert (
        design_lint_power_candidates.UnconnectedComponentPinCandidate
        is design_lint_component_unconnected_pin_candidate_evidence.UnconnectedComponentPinCandidate
    )
    assert (
        component_power_output_candidates.UnconnectedComponentPinCandidate
        is design_lint_component_unconnected_pin_candidate_evidence.UnconnectedComponentPinCandidate
    )
