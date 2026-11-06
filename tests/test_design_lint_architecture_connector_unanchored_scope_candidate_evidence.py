"""Guard typed source ownership for unreviewed connector peer-scope findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_unreviewed_peer_scope_rule_uses_typed_current_source_projection() -> None:
    owner_name = "design_lint_connector_unanchored_scope_evidence.py"
    owner_path = HWREPO / owner_name
    owner = f"kicad_tooling/hwrepo/{owner_name}"
    route_path = HWREPO / "connector_footprint_peer_unanchored_scope_review.py"
    route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=route_path.name)
    route_function = next(
        node
        for node in route_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "unreviewed_unanchored_connector_alias_scope"
    )
    candidate_factory = next(
        node
        for node in route_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_candidate"
    )
    calls = tuple(node for node in ast.walk(candidate_factory) if isinstance(node, ast.Call))
    candidate_builders = tuple(
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "from_source_evidence"
    )
    direct_candidates = tuple(
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "Candidate"
    )
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.footprint_peer_unanchored_scope_unreviewed"
    )
    source_ref = f"{owner}#ConnectorUnanchoredPeerScopeEvidence"
    candidate_ref = f"{owner}#ConnectorUnanchoredPeerScopeCandidate"
    projector_ref = f"{owner}#project_connector_unanchored_peer_scope_evidence"
    scan_source_ref = (
        "kicad_tooling/hwrepo/connector_footprint_peer_pin_types.py#"
        "ConnectorFootprintPeerPinScanSource"
    )
    assignment_refs = {
        "kicad_tooling/hwrepo/netlist_pin_assignments.py#netlist_pin_net_index",
        "kicad_tooling/hwrepo/connector_footprint_peer_assignments.py#connector_footprint_peer_pin_assignments",
    }
    scope_candidate_calls = tuple(
        node
        for node in ast.walk(route_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_candidate"
    )
    source_builders = tuple(
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "from_scan"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
    assert scope_candidate_calls
    assert candidate_builders
    assert source_builders
    assert not direct_candidates
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/connector_footprint_peer_unanchored_scope_review.py#"
        "unreviewed_unanchored_connector_alias_scope"
    )
    assert {
        source_ref,
        candidate_ref,
        projector_ref,
        scan_source_ref,
        *assignment_refs,
    } <= set(rule.implementation_refs)
    assert rule.implementation_owner in rule.implementation_refs
