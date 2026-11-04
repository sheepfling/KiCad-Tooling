"""Guard typed ownership of project-required PCB fitted-reference findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_required_fitted_candidate_evidence import (
    PcbBlockedRequiredFittedReferenceCandidate,
    PcbRequiredFittedReferenceCandidate,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_required_fitted_translation_uses_typed_complete_and_blocked_sources() -> None:
    owner_path = HWREPO / "design_lint_pcb_required_fitted_candidate_evidence.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    translator_path = HWREPO / "design_lint_pcb_required_fitted_reference_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))

    assert PcbRequiredFittedReferenceCandidate.__module__ == (
        "kicad_tooling.hwrepo.design_lint_pcb_required_fitted_candidate_evidence"
    )
    assert (
        PcbBlockedRequiredFittedReferenceCandidate.__module__
        == PcbRequiredFittedReferenceCandidate.__module__
    )
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(translator_path) < IMPLEMENTATION_MAX_LINES
    for name in (
        "project_pcb_required_fitted_reference_evidence",
        "project_blocked_required_fitted_reference_evidence",
    ):
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == name for node in owner_tree.body
        )

    translator_function = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "pcb_required_fitted_reference_candidates"
    )
    typed_owners = {
        node.func.value.id
        for node in ast.walk(translator_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        and isinstance(node.func.value, ast.Name)
    }
    assert typed_owners == {
        "PcbRequiredFittedReferenceCandidate",
        "PcbBlockedRequiredFittedReferenceCandidate",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(translator_function)
    )
