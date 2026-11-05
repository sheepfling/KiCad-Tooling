"""Guard the shared CAN and serial TX-sharing evidence owner."""

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

OWNER_PATH = "kicad_tooling/hwrepo/design_lint_tx_output_sharing_candidate_evidence.py"
RULE_OWNERS = {
    "bus.can_tx_outputs_share_net": (
        "kicad_tooling/hwrepo/can_tx_output_sharing.py#can_tx_output_sharing_candidates"
    ),
    "bus.serial_tx_outputs_share_net": (
        "kicad_tooling/hwrepo/serial_tx_output_sharing.py#serial_tx_output_sharing_candidates"
    ),
}


def test_both_rules_retain_one_bounded_typed_owner_per_source_kind() -> None:
    owner = HWREPO / "design_lint_tx_output_sharing_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    rules = {rule.rule_id: rule for rule in rule_catalog().rules if rule.rule_id in RULE_OWNERS}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert classes >= {
        "CanTxOutputSharingEvidence",
        "SerialTxOutputSharingEvidence",
        "TxOutputSharingCandidate",
    }
    assert set(rules) == set(RULE_OWNERS)
    for rule_id, rule in rules.items():
        assert rule.theme == "interfaces"
        assert rule.implementation_owner == RULE_OWNERS[rule_id]
        assert f"{OWNER_PATH}#TxOutputSharingCandidate" in rule.implementation_refs


def test_protocol_scanners_delegate_candidate_evidence_projection() -> None:
    for module, function_name in (
        ("can_tx_output_sharing.py", "can_tx_output_sharing_candidates"),
        ("serial_tx_output_sharing.py", "serial_tx_output_sharing_candidates"),
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
