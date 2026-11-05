"""Guard typed source ownership for connector peer metadata findings."""

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


def test_connector_peer_metadata_rules_use_the_typed_source_projection() -> None:
    owner_name = "design_lint_connector_footprint_peer_metadata_evidence.py"
    owner = f"kicad_tooling/hwrepo/{owner_name}"
    source_ref = f"{owner}#ConnectorFootprintPeerMetadataEvidence"
    candidate_ref = f"{owner}#ConnectorFootprintPeerMetadataCandidate"
    projector_ref = f"{owner}#project_connector_footprint_peer_metadata_evidence"
    scan_source_ref = (
        "kicad_tooling/hwrepo/connector_footprint_peer_pin_types.py#"
        "ConnectorFootprintPeerPinScanSource"
    )
    assignment_refs = {
        "kicad_tooling/hwrepo/connector_footprint_peer_assignments.py#connector_footprint_peer_pin_net_map",
        "kicad_tooling/hwrepo/connector_footprint_peer_assignments.py#connector_footprint_peer_pin_assignments",
    }
    routes = (
        (
            "connector_footprint_peer_metadata.py",
            "connector_footprint_peer_pin_metadata_assignment_divergences",
            "connector.footprint_peer_pin_metadata_assignment_divergence",
        ),
        (
            "connector_footprint_peer_metadata_open.py",
            "connector_footprint_peer_pin_metadata_open_outliers",
            "connector.footprint_peer_pin_metadata_open_outlier",
        ),
        (
            "connector_footprint_peer_missing_metadata.py",
            "connector_footprint_peer_pin_missing_metadata_assignment_divergences",
            "connector.footprint_peer_pin_missing_metadata_assignment_divergence",
        ),
        (
            "connector_footprint_peer_missing_metadata_open.py",
            "connector_footprint_peer_pin_missing_metadata_open_outliers",
            "connector.footprint_peer_pin_missing_metadata_open_outlier",
        ),
    )
    catalog = {item.rule_id: item for item in rule_catalog().rules}
    owner_path = HWREPO / owner_name

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    for filename, function_name, rule_id in routes:
        route_path = HWREPO / filename
        route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=filename)
        route_function = next(
            node
            for node in route_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        calls = tuple(node for node in ast.walk(route_function) if isinstance(node, ast.Call))
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
            node
            for node in calls
            if (isinstance(node.func, ast.Name) and node.func.id == "Candidate")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "Candidate")
        )
        rule = catalog[rule_id]

        assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
        assert source_builders
        assert candidate_builders
        assert not direct_candidates
        assert rule.implementation_owner == f"kicad_tooling/hwrepo/{filename}#{function_name}"
        assert {
            source_ref,
            candidate_ref,
            projector_ref,
            scan_source_ref,
            *assignment_refs,
        } <= set(rule.implementation_refs)
