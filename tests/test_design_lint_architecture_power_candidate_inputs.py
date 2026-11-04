"""Keep power candidate inputs with their theme and preserve old imports."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_inputs,
    design_lint_power_candidates,
    design_lint_power_inputs,
)
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint, pytest.mark.architecture]


def test_power_candidate_input_lives_in_its_theme_owner() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_power_inputs.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert "PowerCandidateInputs" in definitions


def test_power_services_import_the_owner_and_legacy_paths_reexport_it() -> None:
    owner = "design_lint_power_inputs"
    modules = (
        "design_lint_candidate_inputs",
        "design_lint_power_candidates",
        "design_lint_evaluation_preparation",
    )

    for module_name in modules:
        path = REPO_ROOT / f"kicad_tooling/hwrepo/{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == owner
            and "PowerCandidateInputs" in {alias.name for alias in node.names}
            for node in tree.body
        ), module_name

    assert (
        design_lint_candidate_inputs.PowerCandidateInputs
        is design_lint_power_inputs.PowerCandidateInputs
    )
    assert (
        design_lint_power_candidates.PowerCandidateInputs
        is design_lint_power_inputs.PowerCandidateInputs
    )
