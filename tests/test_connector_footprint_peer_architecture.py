"""Keep footprint-alias grouping and metadata checks in focused modules."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
    pytest.mark.architecture,
]

PEER_MODULES = (
    "connector_footprint_peer_groups.py",
    "connector_footprint_peer_pins.py",
    "connector_footprint_peer_metadata.py",
    "connector_footprint_peer_metadata_open.py",
    "connector_footprint_peer_missing_metadata.py",
    "connector_footprint_peer_missing_metadata_open.py",
)

ALL_OPEN_MODULES = ("connector_footprint_peer_all_open.py",)

ANCHOR_MODULES = ("connector_footprint_peer_anchors.py",)
OPEN_OUTLIER_MODULES = (
    "connector_footprint_peer_open_outliers.py",
    "connector_footprint_peer_open_candidates.py",
    "connector_footprint_open_named_candidates.py",
    "design_lint_connector_footprint_named_open_evidence.py",
)
UNANCHORED_MODULES = (
    "connector_footprint_peer_unanchored_divergence.py",
    "connector_footprint_peer_unanchored_coverage_review.py",
    "design_lint_connector_unanchored_assignment_evidence.py",
    "design_lint_connector_unanchored_source_evidence.py",
    "design_lint_connector_unanchored_coverage_evidence.py",
    "design_lint_connector_unanchored_scope_evidence.py",
)
ASSIGNMENT_MODULES = ("connector_footprint_peer_assignments.py",)


def test_connector_footprint_peer_modules_stay_below_review_limit() -> None:
    sizes = {
        name: line_count(HWREPO / name)
        for name in (
            *PEER_MODULES,
            *ALL_OPEN_MODULES,
            *ANCHOR_MODULES,
            *OPEN_OUTLIER_MODULES,
            *UNANCHORED_MODULES,
            *ASSIGNMENT_MODULES,
        )
    }
    oversized = {name: size for name, size in sizes.items() if size >= IMPLEMENTATION_MAX_LINES}

    assert not oversized, f"Split connector footprint peer modules: {oversized}"


def test_connector_alias_scans_share_candidate_and_inventory_owners() -> None:
    expected_helpers = {
        "connector_footprint_peer_candidate_groups",
        "complete_connector_footprint_peer_pin_inventory",
    }
    for filename in PEER_MODULES[1:]:
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "connector_footprint_peer_groups"
            for alias in node.names
        }
        assert expected_helpers <= imports, (
            f"{filename} duplicated alias grouping or inventory logic"
        )


def test_connector_footprint_peer_candidates_use_typed_projection_owner() -> None:
    owner_path = HWREPO / "design_lint_connector_footprint_candidate_evidence.py"
    service_path = HWREPO / "design_lint_connector_footprint_candidates.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=service_path.name)

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(service_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_connector_footprint_peer_pin_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "ConnectorFootprintPeerPinCandidate"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_connector_footprint_candidate_evidence"
        and "ConnectorFootprintPeerPinCandidate" in {alias.name for alias in node.names}
        for node in service_tree.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(service_tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(service_tree)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(service_tree)
    )


def test_peer_pin_net_index_uses_the_canonical_netlist_owner() -> None:
    index_consumers = (
        "connector_footprint_peer_pins.py",
        "design_lint_connector_footprint_peer_metadata_evidence.py",
        "design_lint_connector_footprint_named_divergence_evidence.py",
        "design_lint_connector_unanchored_source_evidence.py",
    )
    for filename in index_consumers:
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"), filename=filename)
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "netlist_pin_assignments"
            for alias in node.names
        }
        assert "netlist_pin_net_index" in imports, (
            f"{filename} must reuse the canonical source-netlist index"
        )

    assignments = HWREPO / "connector_footprint_peer_assignments.py"
    assignment_tree = ast.parse(assignments.read_text(encoding="utf-8"), filename=assignments.name)
    definitions = {node.name for node in assignment_tree.body if isinstance(node, ast.FunctionDef)}
    assert definitions == {"connector_footprint_peer_pin_assignments"}
    assert "NetlistPinNetIndex" in (HWREPO / "connector_footprint_peer_assignments.py").read_text(
        encoding="utf-8"
    )


def test_all_open_footprint_candidate_owns_anchor_or_reviewed_scope_predicate() -> None:
    owner = HWREPO / "connector_footprint_peer_all_open.py"
    scanner = HWREPO / "connector_footprint_peer_pins.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    scanner_tree = ast.parse(scanner.read_text(encoding="utf-8"), filename=scanner.name)
    functions = {node.name for node in owner_tree.body if isinstance(node, ast.FunctionDef)}
    imported = {
        alias.name
        for node in scanner_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "connector_footprint_peer_all_open"
        for alias in node.names
    }

    assert "generic_footprint_peer_all_open_candidate" in functions
    assert "generic_footprint_peer_all_open_candidate" in imported
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(scanner) < IMPLEMENTATION_MAX_LINES


def test_partial_open_footprint_rule_has_a_focused_candidate_owner() -> None:
    owner = HWREPO / "connector_footprint_peer_open_candidates.py"
    service = HWREPO / "design_lint_connector_footprint_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    service_tree = ast.parse(service.read_text(encoding="utf-8"), filename=service.name)
    functions = {node.name for node in owner_tree.body if isinstance(node, ast.FunctionDef)}
    imports = {
        alias.name
        for node in service_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "connector_footprint_peer_open_candidates"
        for alias in node.names
    }

    assert "footprint_peer_pin_open_outlier_candidates" in functions
    assert "footprint_peer_pin_open_outlier_candidates" in imports
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
