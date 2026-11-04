"""Guard source ownership for mapped regulator and crystal findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_crystal_candidate_evidence,
    design_lint_crystal_candidates,
    design_lint_regulator_candidate_evidence,
    design_lint_regulator_candidates,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
]


def test_mapped_numeric_candidate_translators_use_theme_owned_evidence() -> None:
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
