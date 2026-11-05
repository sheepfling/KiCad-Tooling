"""Guard the shared source route for Ethernet open-pair findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]

OWNER_PATH = "kicad_tooling/hwrepo/design_lint_ethernet_unconnected_candidate_evidence.py"
RULE_IDS = {
    "bus.ethernet_data_unconnected_pin",
    "bus.ethernet_management_unconnected_pin",
}


def test_ethernet_open_pair_rules_share_a_bounded_typed_owner() -> None:
    owner = HWREPO / "design_lint_ethernet_unconnected_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    rules = {rule.rule_id: rule for rule in rule_catalog().rules if rule.rule_id in RULE_IDS}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert classes >= {
        "EthernetDataOpenPairEvidence",
        "EthernetManagementOpenPairEvidence",
        "EthernetUnconnectedCandidate",
    }
    assert set(rules) == RULE_IDS
    for rule in rules.values():
        assert f"{OWNER_PATH}#EthernetUnconnectedCandidate" in rule.implementation_refs


def test_ethernet_open_pair_predicates_delegate_candidate_projection() -> None:
    for module, function_name in (
        ("bus_ethernet_unconnected_data.py", "ethernet_data_unconnected_pin_candidates"),
        (
            "bus_ethernet_unconnected_management.py",
            "ethernet_management_unconnected_pin_candidates",
        ),
    ):
        path = HWREPO / module
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

        assert any(
            isinstance(node.func, ast.Attribute) and node.func.attr == "from_source_evidence"
            for node in calls
        ), module
        assert not any(
            isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
        ), module
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), module
