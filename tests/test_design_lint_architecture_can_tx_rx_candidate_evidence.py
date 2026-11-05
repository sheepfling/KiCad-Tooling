"""Guard typed evidence ownership for CAN TX/RX same-net findings."""

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

OWNER_PATH = "kicad_tooling/hwrepo/design_lint_can_tx_rx_candidate_evidence.py"
RULE_ID = "bus.can_tx_rx_same_net"


def test_can_tx_rx_rule_references_a_bounded_typed_evidence_owner() -> None:
    owner = HWREPO / "design_lint_can_tx_rx_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert classes >= {"CanTxRxEndpoint", "CanTxRxSameNetEvidence", "CanTxRxSameNetCandidate"}
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/can_tx_rx_same_net.py#can_tx_rx_same_net_candidates"
    )
    assert f"{OWNER_PATH}#CanTxRxSameNetCandidate" in rule.implementation_refs


def test_can_tx_rx_predicate_delegates_candidate_evidence_projection() -> None:
    path = HWREPO / "can_tx_rx_same_net.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "can_tx_rx_same_net_candidates"
    )
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    assert any(
        isinstance(node.func, ast.Attribute) and node.func.attr == "from_source_evidence"
        for node in calls
    )
    assert not any(
        isinstance(node.func, ast.Name) and node.func.id == "Candidate" for node in calls
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
    )
