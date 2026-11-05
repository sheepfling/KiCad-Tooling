"""Guard typed ownership for named connector open-peer findings."""

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

RULE_IDS = (
    "connector.footprint_named_power_input_open_outlier",
    "connector.footprint_named_power_output_open_outlier",
    "connector.footprint_named_signal_input_open_outlier",
    "connector.footprint_named_signal_output_open_outlier",
    "connector.footprint_named_passive_open_outlier",
    "connector.footprint_named_signal_mode_dependent_open_outlier",
)


def test_named_open_roles_use_the_typed_scan_and_coverage_owner() -> None:
    owner_name = "design_lint_connector_footprint_named_open_evidence.py"
    owner = f"kicad_tooling/hwrepo/{owner_name}"
    owner_path = HWREPO / owner_name
    adapter_path = HWREPO / "connector_footprint_open_named_candidates.py"
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"), filename=adapter_path.name)
    adapter = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "open_named_outlier_candidates"
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
    catalog = rule_catalog()
    rules = tuple(item for item in catalog.rules if item.rule_id in RULE_IDS)
    required_refs = {
        f"{owner}#ConnectorNamedOpenEvidence",
        f"{owner}#ConnectorNamedOpenCandidate",
        f"{owner}#project_connector_named_open_evidence",
        "kicad_tooling/hwrepo/connector_coverage.py#source_matched_connector_peer_assignment_groups",
        "kicad_tooling/hwrepo/connector_coverage.py#connector_peer_assignment_groups_by_reference",
        "kicad_tooling/hwrepo/connector_footprint_peer_pins.py#scan_connector_footprint_peer_pin_assignments",
    }

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert len(rules) == len(RULE_IDS)
    assert source_builders
    assert candidate_builders
    assert not direct_candidates
    for rule in rules:
        assert rule.implementation_owner in rule.implementation_refs
        assert required_refs <= set(rule.implementation_refs)
