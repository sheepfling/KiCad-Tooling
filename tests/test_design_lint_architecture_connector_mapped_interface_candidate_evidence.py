"""Guard mapped connector-pin candidate source and projection ownership."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
]

_RULE_FUNCTIONS = {
    "unassigned_mapped_interface_signal_pins",
    "unassigned_mapped_interface_power_contacts",
    "unassigned_mapped_interface_shield_pins",
    "unassigned_mapped_interface_other_pins",
    "mapped_other_contacts_on_named_rails",
    "mapped_supply_contacts_on_return_nets",
    "mapped_signal_contacts_on_named_rails",
    "mapped_shield_contacts_on_return_nets",
    "mapped_shield_contacts_on_supply_rails",
}


def test_mapped_interface_evidence_has_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_connector_mapped_interface_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    imports = {
        (node.module, alias.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert ("connector_coverage", "source_matched_connector_pin_evidence") in imports
    assert ("connector_coverage_models", "ConnectorMappedPinEvidence") in imports
    assert ("named_rail_roles", "NamedRailRoleClue") in imports
    assert ("models", "NetlistContract") not in imports
    assert ("connector_mapped_interface_pins", "MappedInterfacePinCandidate") not in imports
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "MappedInterfacePinFindingEvidence"
        for node in tree.body
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_mapped_interface_pin_evidence"
        for node in tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "MappedInterfacePinCandidate"
        for node in tree.body
    )


def test_all_nine_mapped_interface_rules_use_the_typed_candidate_route() -> None:
    adapter = HWREPO / "connector_mapped_interface_pins.py"
    tree = ast.parse(adapter.read_text(encoding="utf-8"), filename=adapter.name)

    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert _RULE_FUNCTIONS <= functions.keys()
    for name in _RULE_FUNCTIONS:
        function = functions[name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_mapped_interface_candidate"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), name
