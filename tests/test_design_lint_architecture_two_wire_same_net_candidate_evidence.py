"""Guard the typed I2C and I3C same-net source owner."""

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

OWNER_PATH = "kicad_tooling/hwrepo/design_lint_two_wire_same_net_candidate_evidence.py"
RULE_OWNERS = {
    "bus.i2c_sda_scl_same_net": (
        "kicad_tooling/hwrepo/i2c_same_net.py#i2c_sda_scl_same_net_candidates"
    ),
    "bus.i3c_sda_scl_same_net": (
        "kicad_tooling/hwrepo/i3c_same_net.py#i3c_sda_scl_same_net_candidates"
    ),
}


def test_i2c_and_i3c_rules_share_a_bounded_typed_evidence_owner() -> None:
    owner = HWREPO / "design_lint_two_wire_same_net_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    rules = {rule.rule_id: rule for rule in rule_catalog().rules if rule.rule_id in RULE_OWNERS}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert classes >= {
        "TwoWirePinEvidence",
        "I2cSameNetEvidence",
        "I3cSameNetEvidence",
        "TwoWireSameNetCandidate",
    }
    assert set(rules) == set(RULE_OWNERS)
    for rule_id, rule in rules.items():
        assert rule.theme == "interfaces"
        assert rule.implementation_owner == RULE_OWNERS[rule_id]
        assert f"{OWNER_PATH}#TwoWireSameNetCandidate" in rule.implementation_refs


def test_i2c_and_i3c_scanners_delegate_candidate_projection() -> None:
    for module, function_name in (
        ("i2c_same_net.py", "i2c_sda_scl_same_net_candidates"),
        ("i3c_same_net.py", "i3c_sda_scl_same_net_candidates"),
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
