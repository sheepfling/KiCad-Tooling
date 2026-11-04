"""Guard shared candidate evidence projection ownership."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_can_candidates,
    design_lint_can_peer_candidate_evidence,
    design_lint_component_peer_candidate_evidence,
    design_lint_component_peer_candidates,
    design_lint_signal_pair_candidate_evidence,
    design_lint_signal_pair_candidates,
    design_lint_unconnected_interface_candidate_evidence,
    design_lint_unconnected_interface_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import CandidateEvidenceProjection
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
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
    "design_lint_signal_pair_candidate_evidence.py",
    "design_lint_component_peer_candidate_evidence.py",
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


def test_signal_pair_candidates_use_their_typed_evidence_owner() -> None:
    owner_path = HWREPO / "design_lint_signal_pair_candidate_evidence.py"
    service_path = HWREPO / "design_lint_signal_pair_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert (
        design_lint_signal_pair_candidates.SignalPairCandidate
        is design_lint_signal_pair_candidate_evidence.SignalPairCandidate
    )
    for function_name in (
        "complementary_signal_candidates",
        "named_differential_pair_candidates",
    ):
        function = next(
            node
            for node in service_tree.body
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
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), function_name
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_signal_pair_evidence"
        for node in owner_tree.body
    )


def test_generic_component_peer_candidate_uses_its_typed_evidence_owner() -> None:
    owner_path = HWREPO / "design_lint_component_peer_candidate_evidence.py"
    service_path = HWREPO / "design_lint_component_peer_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    candidate_builder = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_component_peer_candidate_items"
    )
    outlier_loop = next(
        node
        for node in ast.walk(candidate_builder)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Attribute)
        and node.iter.attr == "outliers"
        and isinstance(node.iter.value, ast.Attribute)
        and node.iter.value.attr == "generic_assignment_outlier"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert (
        design_lint_component_peer_candidates.GenericPeerPinCandidate
        is design_lint_component_peer_candidate_evidence.GenericPeerPinCandidate
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_generic_peer_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(outlier_loop)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(outlier_loop)
    )


@pytest.mark.power_lint
@pytest.mark.evidence_lint
def test_component_peer_power_input_candidates_keep_typed_sources() -> None:
    owner_path = HWREPO / "design_lint_component_peer_candidate_evidence.py"
    service_path = HWREPO / "design_lint_component_peer_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    candidate_builder = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_component_peer_candidate_items"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert (
        design_lint_component_peer_candidates.PowerInputPeerCandidate
        is design_lint_component_peer_candidate_evidence.PowerInputPeerCandidate
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_power_input_peer_evidence"
        for node in owner_tree.body
    )
    assert (
        design_lint_component_peer_candidates.UnconnectedPeerPinCandidate
        is design_lint_component_peer_candidate_evidence.UnconnectedPeerPinCandidate
    )
    assert (
        design_lint_component_peer_candidates.PeerPowerPinDivergenceCandidate
        is design_lint_component_peer_candidate_evidence.PeerPowerPinDivergenceCandidate
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_peer_unconnected_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_peer_power_pin_divergence"
        for node in owner_tree.body
    )
    for scan_name in (
        "power_input_assignment_divergence",
        "named_power_input_assignment_divergence",
        "power_input_open_assignment",
        "named_power_input_all_open",
    ):
        loop = next(
            node
            for node in ast.walk(candidate_builder)
            if isinstance(node, ast.For)
            and ast.unparse(node.iter) == f"peer_pin_scans.{scan_name}.outliers"
        )
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        ), scan_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        ), scan_name
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
