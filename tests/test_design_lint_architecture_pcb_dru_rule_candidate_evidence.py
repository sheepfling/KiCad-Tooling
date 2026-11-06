"""Guard typed source ownership for custom PCB DRC rule findings."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
]


def test_custom_drc_source_records_and_candidates_have_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_pcb_dru_rule_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "SourceBoundPcbDruRuleFile",
        "SourceBoundPcbDruInput",
        "PcbDruRuleFindingEvidence",
        "PcbDruTextVariableFindingEvidence",
        "PcbDruRuleWithoutConstraintFindingEvidence",
        "PcbDruConflictingSeveritiesFindingEvidence",
        "PcbDruRuleCandidate",
        "PcbDruTextVariableCandidate",
        "PcbDruRuleWithoutConstraintCandidate",
        "PcbDruConflictingSeveritiesCandidate",
    } <= classes
    assert {
        "project_pcb_dru_rule_evidence",
        "project_pcb_dru_text_variable_evidence",
        "project_pcb_dru_rule_without_constraint_evidence",
        "project_pcb_dru_conflicting_severities_evidence",
    } <= functions
    parser_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_drc_rule_parser"
        for alias in node.names
    }
    assert {
        "NativeDrcRuleDeclaration",
        "NativeDrcRuleWithSeverity",
        "NativeIgnoredDrcRule",
    } <= parser_imports

    projections = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("project_")
    }
    assert len(projections) == 4
    for function in projections.values():
        assert not any(
            isinstance(node, ast.Attribute) and node.attr == "local_path"
            for node in ast.walk(function)
        )


def test_custom_drc_name_evidence_has_a_separate_focused_owner() -> None:
    owner = HWREPO / "design_lint_pcb_dru_rule_name_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "PcbDruDuplicateRuleNameFindingEvidence",
        "PcbDruCasefoldRuleNameFindingEvidence",
        "PcbDruDuplicateRuleNameCandidate",
        "PcbDruCasefoldRuleNameCandidate",
    } <= classes
    assert {
        "project_pcb_dru_duplicate_rule_name_evidence",
        "project_pcb_dru_casefold_rule_name_evidence",
    } <= functions

    projections = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("project_")
    }
    assert len(projections) == 2
    for function in projections.values():
        assert not any(
            isinstance(node, ast.Attribute) and node.attr == "local_path"
            for node in ast.walk(function)
        )


def test_custom_drc_adapter_only_routes_through_typed_candidate_builders() -> None:
    route = HWREPO / "pcb_dru_rule_review.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)

    assert line_count(route) < IMPLEMENTATION_MAX_LINES
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "_source_bound_rule_file",
        "_source_bound_project_input",
        "_rule_candidate",
        "ignored_custom_drc_rule_candidates",
        "excluded_custom_drc_rule_candidates",
        "text_variable_custom_drc_rule_candidates",
        "custom_drc_rule_without_constraint_candidates",
        "custom_drc_duplicate_rule_name_candidates",
        "custom_drc_casefold_rule_name_collision_candidates",
        "custom_drc_conflicting_severity_candidates",
    } <= functions.keys()

    source_reader = functions["_source_bound_rule_file"]
    assert source_reader.returns is not None
    assert any(
        isinstance(node, ast.Name) and node.id == "SourceBoundPcbDruRuleFile"
        for node in ast.walk(source_reader.returns)
    )

    expected_builders = {
        "ignored_custom_drc_rule_candidates": "_rule_candidate",
        "excluded_custom_drc_rule_candidates": "_rule_candidate",
        "text_variable_custom_drc_rule_candidates": "from_source_evidence",
        "custom_drc_rule_without_constraint_candidates": "_rule_without_constraint_candidate",
        "custom_drc_duplicate_rule_name_candidates": "from_source_evidence",
        "custom_drc_casefold_rule_name_collision_candidates": "from_source_evidence",
        "custom_drc_conflicting_severity_candidates": "from_source_evidence",
    }
    for name, builder in expected_builders.items():
        function = functions[name]
        assert any(
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == builder)
                or (isinstance(node.func, ast.Attribute) and node.func.attr == builder)
            )
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), name

    parser_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_drc_rule_parser"
        for alias in node.names
    }
    assert {
        "native_ignored_rules",
        "native_rule_declarations",
        "native_rules_with_severity",
        "native_rules_with_conflicting_severities",
    } <= parser_imports
