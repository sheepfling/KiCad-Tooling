"""Guard shared candidate evidence projection ownership."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_can_candidates,
    design_lint_can_peer_candidate_evidence,
    design_lint_unconnected_interface_candidate_evidence,
    design_lint_unconnected_interface_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import CandidateEvidenceProjection
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

_THEME_OWNERS = (
    "design_lint_can_termination_candidate_evidence.py",
    "design_lint_can_peer_candidate_evidence.py",
    "design_lint_control_candidate_evidence.py",
    "design_lint_i2c_pullup_candidate_evidence.py",
    "design_lint_i2c_address_candidate_evidence.py",
    "design_lint_usb_data_path_candidate_evidence.py",
    "design_lint_unconnected_interface_candidate_evidence.py",
)


def test_source_projection_container_has_one_shared_owner() -> None:
    shared_owner = HWREPO / "design_lint_types.py"

    assert CandidateEvidenceProjection.__module__ == "kicad_tooling.hwrepo.design_lint_types"
    assert line_count(shared_owner) < IMPLEMENTATION_MAX_LINES
    for filename in _THEME_OWNERS:
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "design_lint_types"
            and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
            for node in tree.body
        ), filename
        assert not any(
            isinstance(node, ast.ClassDef) and node.name.endswith("EvidenceProjection")
            for node in tree.body
        ), filename


def test_candidate_evidence_projection_copies_and_freezes_its_fields() -> None:
    source = {"signal": ("SDA",)}
    projection = CandidateEvidenceProjection(
        rule_id="bus.i2c_missing_pullup",
        evidence=source,
    )
    source["signal"] = ("OTHER",)

    assert projection.evidence == {"signal": ("SDA",)}
    with pytest.raises(TypeError):
        projection.evidence["signal"] = ("OTHER",)  # type: ignore[index]


def test_can_peer_assignment_uses_its_typed_evidence_owner() -> None:
    owner_path = HWREPO / "design_lint_can_peer_candidate_evidence.py"
    service_path = HWREPO / "design_lint_can_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    can_candidates = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "can_candidates"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_can_peer_evidence"
        for node in owner_tree.body
    )
    assert (
        design_lint_can_candidates.CanPeerCandidate
        is design_lint_can_peer_candidate_evidence.CanPeerCandidate
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(can_candidates)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(can_candidates)
    )
    assert line_count(service_path) < IMPLEMENTATION_MAX_LINES


def test_unconnected_protocol_candidates_use_their_typed_evidence_owner() -> None:
    owner_path = HWREPO / "design_lint_unconnected_interface_candidate_evidence.py"
    service_path = HWREPO / "design_lint_unconnected_interface_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    candidate_builder = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "unconnected_interface_candidates"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert (
        design_lint_unconnected_interface_candidates.UnconnectedInterfaceCandidate
        is design_lint_unconnected_interface_candidate_evidence.UnconnectedInterfaceCandidate
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_unconnected_interface_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(candidate_builder)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(candidate_builder)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence"
        for node in ast.walk(candidate_builder)
    )
