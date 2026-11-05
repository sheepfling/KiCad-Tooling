"""Guard typed source ownership for unanchored coverage findings."""

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


def test_unanchored_coverage_rule_uses_the_typed_source_projection() -> None:
    owner_name = "design_lint_connector_unanchored_coverage_evidence.py"
    owner = f"kicad_tooling/hwrepo/{owner_name}"
    owner_path = HWREPO / owner_name
    route_path = HWREPO / "connector_footprint_peer_unanchored_coverage_review.py"
    route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=route_path.name)
    factory = next(
        node
        for node in route_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_candidate"
    )
    calls = tuple(node for node in ast.walk(factory) if isinstance(node, ast.Call))
    source_builders = tuple(
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "from_scan"
    )
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
        if item.rule_id == "connector.footprint_peer_unanchored_scope_coverage_missing"
    )
    source_ref = f"{owner}#ConnectorUnanchoredCoverageEvidence"
    candidate_ref = f"{owner}#ConnectorUnanchoredCoverageCandidate"
    projector_ref = f"{owner}#project_connector_unanchored_coverage_evidence"
    validator_ref = (
        "kicad_tooling/hwrepo/design_lint_connector_unanchored_source_evidence.py#"
        "validate_current_unanchored_peer_contacts"
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
    assert source_builders
    assert candidate_builders
    assert not direct_candidates
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/connector_footprint_peer_unanchored_coverage_review.py#"
        "uncovered_unanchored_connector_alias_scope"
    )
    assert {source_ref, candidate_ref, projector_ref, validator_ref} <= set(
        rule.implementation_refs
    )
    assert rule.implementation_owner in rule.implementation_refs
