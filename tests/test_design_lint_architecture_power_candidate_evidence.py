"""Guard the typed evidence route for power and supply candidate sources."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]

_SOURCE_LOOPS = {
    "same_voltage_power_inputs_on_different_nets",
    "ic_power_rails_without_fitted_capacitors",
    "power_inputs_without_supported_source_paths",
    "connector_capacitor_only_nets",
    "component_supply_pins_on_different_nets",
    "numbered_power_rail_groups",
}


def test_power_source_projections_have_a_small_typed_owner() -> None:
    owner = HWREPO / "design_lint_power_candidate_evidence.py"
    adapter = HWREPO / "design_lint_power_candidates.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_power_candidate_evidence"
        for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "PowerCandidate" for node in owner_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and "CandidateEvidenceProjection" in {alias.name for alias in node.names}
        for node in owner_tree.body
    )


def test_each_power_source_loop_uses_the_typed_projection_adapter() -> None:
    path = HWREPO / "design_lint_power_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    scan = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "scan_power_candidates"
    )
    loops = {
        node.iter.func.id: node
        for node in ast.walk(scan)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
    }

    assert _SOURCE_LOOPS <= loops.keys()
    for source_name in _SOURCE_LOOPS:
        loop = loops[source_name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(loop)
        ), source_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(loop)
        ), source_name


def test_power_pin_role_rules_use_bounded_source_evidence() -> None:
    source_owner = HWREPO / "design_lint_power_pin_role_evidence.py"
    source_tree = ast.parse(source_owner.read_text(encoding="utf-8"), filename=source_owner.name)
    source_classes = {node.name for node in source_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(source_owner) < IMPLEMENTATION_MAX_LINES
    assert source_classes >= {
        "NamedPowerPinNetRoleConflictEvidence",
        "NamedSupplyPinNegativeRailEvidence",
    }

    routes = {
        "power_pin_net_roles.py": (
            "named_power_pin_net_role_conflicts",
            "power.pin_function_net_role_conflict",
            "NamedPowerPinNetRoleConflictEvidence",
        ),
        "power_negative_rail.py": (
            "positive_supply_pins_on_negative_rails",
            "power.named_supply_pin_on_negative_rail",
            "NamedSupplyPinNegativeRailEvidence",
        ),
    }
    for filename, (function_name, rule_id, evidence_name) in routes.items():
        path = HWREPO / filename
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
        ), function_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), function_name

        rule = rule_catalog(rule_id=rule_id).rules[0]
        assert "kicad_tooling/hwrepo/design_lint_power_candidate_evidence.py#PowerCandidate" in (
            rule.implementation_refs
        )
        assert (
            f"kicad_tooling/hwrepo/design_lint_power_pin_role_evidence.py#{evidence_name}"
            in rule.implementation_refs
        )


def test_authored_power_map_rules_use_bounded_source_evidence() -> None:
    routes = {
        "design_lint_power_decoupling.py": (
            "ic_decoupling_candidates",
            "power.ic_decoupling_below_project_minimum",
            "kicad_tooling/hwrepo/design_lint_ic_decoupling_candidate_evidence.py#IcDecouplingFindingEvidence",
        ),
        "design_lint_power_regulator_passives.py": (
            "regulator_required_passive_candidates",
            "power.regulator_required_passive_topology_mismatch",
            "kicad_tooling/hwrepo/design_lint_regulator_passive_candidate_evidence.py#RegulatorPassiveTopologyFindingEvidence",
        ),
        "design_lint_power_regulator_pin_roles.py": (
            "regulator_pin_role_candidates",
            "power.regulator_pin_role_mismatch",
            "kicad_tooling/hwrepo/design_lint_regulator_passive_candidate_evidence.py#RegulatorPassivePinRoleFindingEvidence",
        ),
        "design_lint_power_regulator_support_roles.py": (
            "regulator_support_pin_role_candidates",
            "power.regulator_support_pin_role_mismatch",
            "kicad_tooling/hwrepo/design_lint_regulator_support_candidate_evidence.py#RegulatorSupportPinRoleFindingEvidence",
        ),
    }
    source_owners = (
        "design_lint_ic_decoupling_candidate_evidence.py",
        "design_lint_regulator_passive_candidate_evidence.py",
        "design_lint_regulator_support_candidate_evidence.py",
    )
    for filename in (*source_owners, *routes):
        assert line_count(HWREPO / filename) < IMPLEMENTATION_MAX_LINES

    for filename, (function_name, rule_id, source_reference) in routes.items():
        path = HWREPO / filename
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
        ), function_name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), function_name

        rule = rule_catalog(rule_id=rule_id).rules[0]
        assert source_reference in rule.implementation_refs
        assert "kicad_tooling/hwrepo/design_lint_power_candidate_evidence.py#PowerCandidate" in (
            rule.implementation_refs
        )
        assert (
            "kicad_tooling/hwrepo/design_lint_power_candidate_evidence.py#project_power_candidate_evidence"
            in rule.implementation_refs
        )
        expected_validation_owner = {
            "power.ic_decoupling_below_project_minimum": (
                "kicad_tooling/hwrepo/design_lint_ic_decoupling_candidate_evidence.py#review_ic_decoupling_requirement"
            ),
            "power.regulator_required_passive_topology_mismatch": (
                "kicad_tooling/hwrepo/regulator_passive_checks.py#regulator_passive_topology_issues"
            ),
            "power.regulator_pin_role_mismatch": (
                "kicad_tooling/hwrepo/regulator_passive_checks.py#regulator_passive_pin_role_issues"
            ),
            "power.regulator_support_pin_role_mismatch": (
                "kicad_tooling/hwrepo/regulator_support_checks.py#regulator_support_pin_role_issues"
            ),
        }[rule_id]
        assert expected_validation_owner in rule.implementation_refs
