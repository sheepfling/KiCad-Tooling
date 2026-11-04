"""Guard typed ownership of signal-path DRC coverage findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_signal_path_coverage_evidence import (
    PcbSignalPathCoverageCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_signal_path_coverage_candidate_has_one_typed_source_owner() -> None:
    owner_path = HWREPO / "design_lint_pcb_signal_path_coverage_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_requirement_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbSignalPathCoverageCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_signal_path_coverage_evidence"
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "project_pcb_signal_path_coverage_evidence"
        for node in owner_tree.body
    )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_requirement_coverage_candidates"
    )
    typed_calls = [
        node
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "PcbSignalPathCoverageCandidate"
    ]
    assert len(typed_calls) == 1
    opaque_path_candidates = [
        node
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        and any(
            keyword.arg == "rule_id"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "pcb.signal_path_rule_coverage"
            for keyword in node.keywords
        )
    ]
    assert opaque_path_candidates == []
