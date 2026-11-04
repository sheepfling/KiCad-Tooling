"""Guard source and projection ownership for PCB DRC severity findings."""

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

_CANDIDATE_BUILDERS = {
    "ignored_core_native_drc_check_candidates",
    "ignored_dfm_native_drc_check_candidates",
    "warning_core_native_drc_check_candidates",
    "warning_dfm_native_drc_check_candidates",
    "ignored_warning_default_native_drc_check_candidates",
    "_downgraded_native_drc_check_candidates",
}
_RULE_IMPLEMENTATIONS = {
    "ignored_core_native_drc_check_candidates",
    "ignored_dfm_native_drc_check_candidates",
    "warning_core_native_drc_check_candidates",
    "warning_dfm_native_drc_check_candidates",
    "ignored_warning_default_native_drc_check_candidates",
    "downgraded_signal_integrity_drc_check_candidates",
    "downgraded_electrical_drc_check_candidates",
    "downgraded_miscellaneous_drc_check_candidates",
}
_DELEGATED_RULE_IMPLEMENTATIONS = {
    "downgraded_signal_integrity_drc_check_candidates",
    "downgraded_electrical_drc_check_candidates",
    "downgraded_miscellaneous_drc_check_candidates",
}


def test_drc_severity_source_and_candidate_have_a_focused_owner() -> None:
    owner = HWREPO / "design_lint_pcb_drc_global_severity_candidate_evidence.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "SourceBoundPcbDrcSettings",
        "PcbDrcSeverityFindingEvidence",
        "PcbDrcSeverityCandidate",
    } <= classes
    assert "project_pcb_drc_severity_evidence" in functions
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pcb_drc_project_settings"
        and any(alias.name == "PcbDrcCheckSeverity" for alias in node.names)
        for node in tree.body
    )

    parser = HWREPO / "pcb_drc_project_settings.py"
    parser_tree = ast.parse(parser.read_text(encoding="utf-8"), filename=parser.name)
    assert line_count(parser) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "PcbDrcCheckSeverity"
        for node in parser_tree.body
    )
    parser_functions = {
        node.name: node for node in parser_tree.body if isinstance(node, ast.FunctionDef)
    }
    for name in (
        "configured_core_drc_check_severities",
        "configured_dfm_drc_check_severities",
        "configured_signal_integrity_drc_check_severities",
        "configured_electrical_drc_check_severities",
        "configured_miscellaneous_drc_check_severities",
        "configured_warning_default_drc_check_severities",
    ):
        annotation = parser_functions[name].returns
        assert annotation is not None
        assert any(
            isinstance(node, ast.Name) and node.id == "PcbDrcCheckSeverity"
            for node in ast.walk(annotation)
        ), name


def test_all_drc_severity_candidates_use_typed_source_projection() -> None:
    route = HWREPO / "pcb_drc_global_severity_review.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)

    assert line_count(route) < IMPLEMENTATION_MAX_LINES
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert _CANDIDATE_BUILDERS <= functions.keys()
    for name in _CANDIDATE_BUILDERS:
        function = functions[name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_severity_candidate"
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

    source_reader = functions["_source_bound_drc_settings"]
    assert source_reader.returns is not None
    assert any(
        isinstance(node, ast.Name) and node.id == "SourceBoundPcbDrcSettings"
        for node in ast.walk(source_reader.returns)
    )


def test_every_catalog_rule_implementation_reaches_the_typed_candidate_builder() -> None:
    route = HWREPO / "pcb_drc_global_severity_review.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert _RULE_IMPLEMENTATIONS <= functions.keys()
    for name in _RULE_IMPLEMENTATIONS:
        function = functions[name]
        expected_builder = (
            "_downgraded_native_drc_check_candidates"
            if name in _DELEGATED_RULE_IMPLEMENTATIONS
            else "_severity_candidate"
        )
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == expected_builder
            for node in ast.walk(function)
        ), name
        assert not any(
            isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(function)
        ), name
