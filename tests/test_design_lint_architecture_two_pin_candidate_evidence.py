"""Guard the typed source owner for same-net two-pin candidates."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def test_two_pin_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_two_pin_candidate_evidence.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_two_pin_component_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "TwoPinSameNetCandidate"
        for node in owner_tree.body
    )


def test_two_pin_adapter_routes_through_the_typed_projection_owner() -> None:
    path = HWREPO / "design_lint_component_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "TwoPinSameNetCandidate"
        and node.func.attr == "from_source_evidence"
    ]

    assert len(calls) == 1
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(calls[0])
    )


def test_two_pin_scan_and_projector_retain_the_native_source() -> None:
    scan_path = HWREPO / "two_pin_components.py"
    scan_tree = ast.parse(scan_path.read_text(encoding="utf-8"), filename=scan_path.name)
    owner_path = HWREPO / "design_lint_two_pin_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)

    assert any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "source_netlist"
        for node in ast.walk(scan_tree)
    )
    assert any(
        isinstance(node, ast.keyword)
        and node.arg == "source_netlist"
        and isinstance(node.value, ast.Name)
        and node.value.id == "observed"
        for node in ast.walk(scan_tree)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "two_pin_component_is_current"
        for node in ast.walk(owner_tree)
    )


def test_specialized_two_pin_adapters_reuse_the_typed_projection_owner() -> None:
    modules = (
        "two_pin_leds.py",
        "two_pin_buzzers.py",
        "two_pin_speakers.py",
        "two_pin_batteries.py",
        "two_pin_motors.py",
        "two_pin_solar_cells.py",
        "two_pin_thermocouples.py",
    )
    for module in modules:
        path = HWREPO / module
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        typed_routes = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "TwoPinSameNetCandidate"
        ]

        assert len(typed_routes) == 1, module
        assert not any(
            isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
        ), module
