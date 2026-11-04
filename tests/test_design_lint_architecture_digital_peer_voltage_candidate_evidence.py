"""Guard the shared typed projection for SPI and serial peer-voltage findings."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_digital_peer_voltage_evidence_has_a_shared_small_owner() -> None:
    owner = HWREPO / "design_lint_digital_peer_voltage_candidate_evidence.py"
    adapters = (
        HWREPO / "design_lint_digital_peer_voltage_candidates.py",
        HWREPO / "design_lint_serial_peer_candidates.py",
    )
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert all(line_count(adapter) < IMPLEMENTATION_MAX_LINES for adapter in adapters)
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_digital_peer_voltage_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "DigitalPeerVoltageCandidate"
        for node in owner_tree.body
    )


@pytest.mark.parametrize(
    ("filename", "function_name", "expected_loop_count"),
    [
        pytest.param(
            "design_lint_digital_peer_voltage_candidates.py",
            "digital_peer_voltage_candidates",
            2,
            id="spi-and-serial-adapter",
        ),
        pytest.param(
            "design_lint_serial_peer_candidates.py",
            "serial_voltage_candidates",
            1,
            id="serial-peer-adapter",
        ),
    ],
)
def test_peer_voltage_adapters_route_each_review_through_typed_evidence(
    filename: str,
    function_name: str,
    expected_loop_count: int,
) -> None:
    path = HWREPO / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    loops = [node for node in ast.walk(adapter) if isinstance(node, ast.For)]

    assert len(loops) == expected_loop_count
    assert all(
        any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        )
        for loop in loops
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(adapter)
    )
