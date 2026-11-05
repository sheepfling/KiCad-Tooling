"""Guard source ownership for reviewed unanchored connector assignments."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_reviewed_unanchored_assignment_uses_typed_current_sources() -> None:
    owner_name = "design_lint_connector_unanchored_assignment_evidence.py"
    owner = f"kicad_tooling/hwrepo/{owner_name}"
    owner_path = HWREPO / owner_name
    adapter_path = HWREPO / "connector_footprint_peer_unanchored_divergence.py"
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"), filename=adapter_path.name)
    adapter = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "reviewed_unanchored_connector_alias_divergences"
    )
    calls = tuple(node for node in ast.walk(adapter) if isinstance(node, ast.Call))
    direct_candidates = tuple(
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "Candidate"
    )
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
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.footprint_peer_pin_unanchored_assignment_divergence"
    )
    expected_refs = {
        f"{owner}#ConnectorUnanchoredAssignmentEvidence",
        f"{owner}#ConnectorUnanchoredAssignmentCandidate",
        f"{owner}#project_connector_unanchored_assignment_evidence",
        "kicad_tooling/hwrepo/connector_coverage.py#source_matched_connector_peer_assignment_groups",
        "kicad_tooling/hwrepo/design_lint_connector_unanchored_source_evidence.py#validate_current_unanchored_peer_contacts",
    }

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert source_builders
    assert candidate_builders
    assert not direct_candidates
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/connector_footprint_peer_unanchored_divergence.py#"
        "reviewed_unanchored_connector_alias_divergences"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert expected_refs <= set(rule.implementation_refs)
