"""Guard typed source projections for serial peer candidate builders."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.evidence_lint,
]


def test_serial_peer_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_serial_peer_candidate_evidence.py"
    adapter = HWREPO / "design_lint_serial_peer_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_serial_peer_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "SerialPeerCandidate"
        for node in owner_tree.body
    )


@pytest.mark.parametrize(
    ("function_name", "candidate_type", "source_type", "owner_module"),
    [
        pytest.param(
            "serial_unmapped_peer_candidates",
            "SerialPeerCandidate",
            "UnmappedSerialPeerFindingEvidence",
            "design_lint_serial_peer_candidate_evidence",
            id="unmapped-peer",
        ),
        pytest.param(
            "serial_reference_candidates",
            "SerialPeerCandidate",
            "SerialPeerReferenceFindingEvidence",
            "design_lint_serial_peer_candidate_evidence",
            id="reference-review",
        ),
        pytest.param(
            "serial_voltage_candidates",
            "DigitalPeerVoltageCandidate",
            "DigitalPeerVoltageFindingEvidence",
            "design_lint_digital_peer_voltage_candidate_evidence",
            id="serial-voltage-review",
        ),
    ],
)
def test_serial_candidate_builders_use_typed_projection_adapters(
    function_name: str,
    candidate_type: str,
    source_type: str,
    owner_module: str,
) -> None:
    path = HWREPO / "design_lint_serial_peer_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == candidate_type
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(function)
    ), function_name
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == source_type
        for node in ast.walk(function)
    ), function_name
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    ), function_name
    assert source_type in {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == owner_module
        for alias in node.names
    }
    assert candidate_type in {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == owner_module
        for alias in node.names
    }
