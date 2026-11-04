"""Guard schematic candidate evidence ownership and adapter boundaries."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
]


def test_schematic_candidate_projection_has_one_bounded_owner() -> None:
    owner = HWREPO / "design_lint_schematic_geometry_candidate_evidence.py"
    adapter = HWREPO / "design_lint_schematic_geometry.py"

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    adapter_tree = ast.parse(adapter.read_text(encoding="utf-8"), filename=adapter.name)

    assert any(
        isinstance(node, ast.ClassDef) and node.name == "SchematicPinGeometryCandidate"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "SchematicWireTopologyCandidate"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "SchematicLabelEndpointCandidate"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_schematic_pin_geometry_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_schematic_wire_topology_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_schematic_label_endpoint_evidence"
        for node in owner_tree.body
    )
    typed_rules = {
        "schematic.wire_end_on_pin_line",
        "schematic.pin_tip_on_wire_interior",
        "schematic.wire_endpoint_near_pin_tip",
        "schematic.unmarked_wire_crossing",
        "schematic.unmarked_t_junction",
        "schematic.label_near_wire_endpoint",
    }
    direct_candidate_rules = {
        keyword.value.value
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for keyword in node.keywords
        if keyword.arg == "rule_id"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }
    assert not direct_candidate_rules & typed_rules
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "source_bindings"
        for node in ast.walk(adapter_tree)
    )
    assert "schematic_geometry_evidence" in adapter.read_text(encoding="utf-8")
    assert "SchematicPinGeometryCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicWireTopologyCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicLabelEndpointCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
