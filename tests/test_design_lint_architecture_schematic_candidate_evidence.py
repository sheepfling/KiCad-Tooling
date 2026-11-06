"""Guard schematic candidate evidence ownership and adapter boundaries."""

from __future__ import annotations

import ast
from dataclasses import fields
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry_candidate_evidence import (
    SchematicGeometrySourceIdentity,
    schematic_geometry_source_identity,
)
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
    assert "def schematic_geometry_source_identity" in owner.read_text(encoding="utf-8")
    assert "schematic_geometry_source_identity" in text_owner.read_text(encoding="utf-8")
    assert "schematic_geometry_source_identity" in body_owner.read_text(encoding="utf-8")
    assert "SchematicPinGeometryCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicWireTopologyCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )
    assert "SchematicLabelEndpointCandidate.from_source_evidence" in adapter.read_text(
        encoding="utf-8"
    )


def test_shared_schematic_source_identity_has_a_named_immutable_contract() -> None:
    expected_fields = (
        "source_path",
        "source_sha256",
        "sheet_instance_path",
        "sheet_path",
        "root_source_path",
        "root_source_sha256",
        "source_tree_sha256",
    )

    assert tuple(field.name for field in fields(SchematicGeometrySourceIdentity)) == expected_fields
    assert (
        get_type_hints(schematic_geometry_source_identity)["return"]
        is SchematicGeometrySourceIdentity
    )
    assert get_type_hints(SchematicGeometrySourceIdentity) == {
        field: str for field in expected_fields
    }

    identity = SchematicGeometrySourceIdentity(
        source_path="Projects/Child.kicad_sch",
        source_sha256="a" * 64,
        sheet_instance_path="root/child",
        sheet_path="Child",
        root_source_path="Projects/Root.kicad_sch",
        root_source_sha256="b" * 64,
        source_tree_sha256="c" * 64,
    )
    report_fields = identity.report_fields()
    assert tuple(report_fields) == (
        "schematic",
        "schematic_sha256",
        "sheet_instance_path",
        "sheet_path",
        "schematic_root",
        "schematic_root_sha256",
        "schematic_tree_sha256",
    )
    assert report_fields["schematic"] == ("Projects/Child.kicad_sch",)
    assert report_fields["sheet_path"] == ("Child",)
    with pytest.raises(TypeError):
        report_fields["schematic"] = ("stale.kicad_sch",)  # type: ignore[index]
