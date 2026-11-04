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


def test_schematic_candidate_projection_has_bounded_theme_owners() -> None:
    owner = HWREPO / "design_lint_schematic_geometry_candidate_evidence.py"
    text_owner = HWREPO / "design_lint_schematic_text_candidate_evidence.py"
    body_owner = HWREPO / "design_lint_schematic_symbol_body_candidate_evidence.py"
    adapter = HWREPO / "design_lint_schematic_geometry.py"

    assert all(
        line_count(path) < IMPLEMENTATION_MAX_LINES for path in (owner, text_owner, body_owner)
    )
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    text_tree = ast.parse(text_owner.read_text(encoding="utf-8"), filename=text_owner.name)
    body_tree = ast.parse(body_owner.read_text(encoding="utf-8"), filename=body_owner.name)
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
        isinstance(node, ast.ClassDef) and node.name == "SchematicTextGeometryCandidate"
        for node in text_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "SchematicSymbolBodyObstructionCandidate"
        for node in body_tree.body
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
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_schematic_text_geometry_evidence"
        for node in text_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_schematic_symbol_body_evidence"
        for node in body_tree.body
    )
    direct_candidate_calls = [
        node
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]
    assert direct_candidate_calls == []
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "source_bindings"
        for node in ast.walk(adapter_tree)
    )
    assert "def schematic_geometry_evidence" in owner.read_text(encoding="utf-8")
    assert "schematic_geometry_evidence" in text_owner.read_text(encoding="utf-8")
    assert "schematic_geometry_evidence" in body_owner.read_text(encoding="utf-8")
    assert "SchematicPinGeometryCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicWireTopologyCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicLabelEndpointCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
