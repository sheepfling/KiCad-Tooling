"""Guard source ownership for mapped regulator and crystal findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_connector_named_peer_return_split_candidate_evidence,
    design_lint_connector_named_peer_signal_split_candidate_evidence,
    design_lint_connector_named_peer_supply_split_candidate_evidence,
    design_lint_connectors_named_peer_return_splits,
    design_lint_connectors_named_peer_signal_splits,
    design_lint_connectors_named_peer_supply_splits,
    design_lint_crystal_candidate_evidence,
    design_lint_crystal_candidates,
    design_lint_power_path_candidate_evidence,
    design_lint_power_path_candidates,
    design_lint_power_sequence_candidate_evidence,
    design_lint_power_sequence_candidates,
    design_lint_protection_candidate_evidence,
    design_lint_protection_candidates,
    design_lint_rc_filter_candidate_evidence,
    design_lint_rc_filter_candidates,
    design_lint_regulator_candidate_evidence,
    design_lint_regulator_candidates,
    power_path_models,
    power_sequence_models,
)
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
]


def test_mapped_candidate_translators_use_theme_owned_evidence() -> None:
    owners = (
        (
            design_lint_regulator_candidate_evidence,
            design_lint_regulator_candidate_evidence.RegulatorFeedbackCandidate,
            design_lint_regulator_candidates,
            "regulator_feedback_candidates",
            "project_regulator_feedback_evidence",
        ),
        (
            design_lint_crystal_candidate_evidence,
            design_lint_crystal_candidate_evidence.CrystalNetworkCandidate,
            design_lint_crystal_candidates,
            "crystal_network_candidates",
            "project_crystal_network_evidence",
        ),
        (
            design_lint_rc_filter_candidate_evidence,
            design_lint_rc_filter_candidate_evidence.RcFilterCandidate,
            design_lint_rc_filter_candidates,
            "rc_filter_candidates",
            "project_rc_filter_evidence",
        ),
        (
            design_lint_power_path_candidate_evidence,
            design_lint_power_path_candidate_evidence.PowerPathCandidate,
            design_lint_power_path_candidates,
            "power_path_candidates",
            "project_power_path_evidence",
        ),
        (
            design_lint_protection_candidate_evidence,
            design_lint_protection_candidate_evidence.UnreviewedProtectionCandidate,
            design_lint_protection_candidates,
            "protection_candidates",
            "project_unreviewed_protection_evidence",
        ),
        (
            design_lint_protection_candidate_evidence,
            design_lint_protection_candidate_evidence.ProtectionMismatchCandidate,
            design_lint_protection_candidates,
            "protection_candidates",
            "project_protection_mismatch_evidence",
        ),
        (
            design_lint_power_sequence_candidate_evidence,
            design_lint_power_sequence_candidate_evidence.PowerSequenceCandidate,
            design_lint_power_sequence_candidates,
            "power_sequence_candidates",
            "project_power_sequence_evidence",
        ),
    )

    for module, candidate_type, translator_module, translator_name, projector_name in owners:
        owner_path = HWREPO / f"{module.__name__.rsplit('.', 1)[-1]}.py"
        translator_path = HWREPO / f"{translator_module.__name__.rsplit('.', 1)[-1]}.py"
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))
        translator = next(
            node
            for node in translator_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == translator_name
        )

        assert candidate_type.__module__ == module.__name__
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == projector_name
            for node in owner_tree.body
        )
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(translator)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(translator)
        )
        assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
        assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES


def test_power_path_and_sequence_map_identity_have_shared_domain_owners() -> None:
    identity_path = HWREPO / "power_path_models.py"
    coverage_path = HWREPO / "design_lint_mapped_topology_coverage.py"
    candidate_path = HWREPO / "design_lint_power_path_candidates.py"
    sequence_identity_path = HWREPO / "power_sequence_models.py"
    identity_tree = ast.parse(identity_path.read_text(encoding="utf-8"))
    coverage_tree = ast.parse(coverage_path.read_text(encoding="utf-8"))
    candidate_tree = ast.parse(candidate_path.read_text(encoding="utf-8"))
    sequence_identity_tree = ast.parse(sequence_identity_path.read_text(encoding="utf-8"))
    sequence_evidence_path = HWREPO / "design_lint_power_sequence_candidate_evidence.py"
    sequence_evidence_tree = ast.parse(sequence_evidence_path.read_text(encoding="utf-8"))

    assert power_path_models.power_path_map_sha256.__module__ == power_path_models.__name__
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "power_path_map_sha256"
        for node in identity_tree.body
    )
    for tree in (coverage_tree, candidate_tree):
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "power_path_map_sha256"
            for node in ast.walk(tree)
        )
    assert line_count(identity_path) < IMPLEMENTATION_MAX_LINES
    assert power_sequence_models.power_sequence_map_sha256.__module__ == (
        power_sequence_models.__name__
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "power_sequence_map_sha256"
        for node in sequence_identity_tree.body
    )
    for tree in (coverage_tree, sequence_evidence_tree):
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "power_sequence_map_sha256"
            for node in ast.walk(tree)
        )
    assert line_count(sequence_identity_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(sequence_evidence_path) < IMPLEMENTATION_MAX_LINES


def test_named_peer_return_rule_has_a_focused_source_bound_owner() -> None:
    owner_module = design_lint_connectors_named_peer_return_splits
    evidence_module = design_lint_connector_named_peer_return_split_candidate_evidence
    owner_path = HWREPO / "design_lint_connectors_named_peer_return_splits.py"
    evidence_path = HWREPO / "design_lint_connector_named_peer_return_split_candidate_evidence.py"
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.mapped_named_peer_return_split_nets"
    )
    owner = (
        "kicad_tooling/hwrepo/design_lint_connectors_named_peer_return_splits.py"
        "#mapped_named_peer_return_split_net_candidates"
    )
    projector = (
        "kicad_tooling/hwrepo/design_lint_connector_named_peer_return_split_candidate_evidence.py"
        "#project_mapped_named_peer_return_split_evidence"
    )

    assert owner_module.mapped_named_peer_return_split_net_candidates.__module__ == (
        owner_module.__name__
    )
    assert (
        evidence_module.MappedNamedPeerReturnSplitCandidate.__module__ == evidence_module.__name__
    )
    assert rule.theme == "connectors"
    assert rule.implementation_owner == owner
    assert rule.implementation_owner in rule.implementation_refs
    assert projector in rule.implementation_refs
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence_path) < IMPLEMENTATION_MAX_LINES


def test_named_peer_supply_rule_has_a_focused_source_bound_owner() -> None:
    owner_module = design_lint_connectors_named_peer_supply_splits
    evidence_module = design_lint_connector_named_peer_supply_split_candidate_evidence
    owner_path = HWREPO / "design_lint_connectors_named_peer_supply_splits.py"
    evidence_path = HWREPO / "design_lint_connector_named_peer_supply_split_candidate_evidence.py"
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.mapped_named_peer_supply_split_nets"
    )
    owner = (
        "kicad_tooling/hwrepo/design_lint_connectors_named_peer_supply_splits.py"
        "#mapped_named_peer_supply_split_net_candidates"
    )
    projector = (
        "kicad_tooling/hwrepo/design_lint_connector_named_peer_supply_split_candidate_evidence.py"
        "#project_mapped_named_peer_supply_split_evidence"
    )

    assert owner_module.mapped_named_peer_supply_split_net_candidates.__module__ == (
        owner_module.__name__
    )
    assert (
        evidence_module.MappedNamedPeerSupplySplitCandidate.__module__ == evidence_module.__name__
    )
    assert rule.theme == "connectors"
    assert rule.implementation_owner == owner
    assert rule.implementation_owner in rule.implementation_refs
    assert projector in rule.implementation_refs
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence_path) < IMPLEMENTATION_MAX_LINES


def test_named_peer_signal_rule_has_a_focused_source_bound_owner() -> None:
    owner_module = design_lint_connectors_named_peer_signal_splits
    evidence_module = design_lint_connector_named_peer_signal_split_candidate_evidence
    owner_path = HWREPO / "design_lint_connectors_named_peer_signal_splits.py"
    evidence_path = HWREPO / "design_lint_connector_named_peer_signal_split_candidate_evidence.py"
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.mapped_named_peer_signal_split_nets"
    )
    owner = (
        "kicad_tooling/hwrepo/design_lint_connectors_named_peer_signal_splits.py"
        "#mapped_named_peer_signal_split_net_candidates"
    )
    projector = (
        "kicad_tooling/hwrepo/design_lint_connector_named_peer_signal_split_candidate_evidence.py"
        "#project_mapped_named_peer_signal_split_evidence"
    )

    assert owner_module.mapped_named_peer_signal_split_net_candidates.__module__ == (
        owner_module.__name__
    )
    assert (
        evidence_module.MappedNamedPeerSignalSplitCandidate.__module__ == evidence_module.__name__
    )
    assert rule.theme == "connectors"
    assert rule.implementation_owner == owner
    assert rule.implementation_owner in rule.implementation_refs
    assert projector in rule.implementation_refs
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(evidence_path) < IMPLEMENTATION_MAX_LINES
