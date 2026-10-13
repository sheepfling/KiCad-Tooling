"""Architecture boundaries for explicit fitted-reference checks."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import pcb_required_fitted_reference_models
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
]


def test_required_fitted_models_and_predicate_stay_in_pcb_theme_owners() -> None:
    model_path = HWREPO / "pcb_required_fitted_reference_models.py"
    predicate_path = HWREPO / "pcb_required_fitted_reference_checks.py"
    candidate_path = HWREPO / "design_lint_pcb_required_fitted_reference_candidates.py"
    report_path = HWREPO / "design_lint_pcb_required_fitted_reference_report.py"

    assert all(
        line_count(path) < IMPLEMENTATION_MAX_LINES
        for path in (model_path, predicate_path, candidate_path, report_path)
    )
    assert not hasattr(shared_models, "PcbRequiredFittedReferenceMap")
    assert not hasattr(shared_models, "PcbRequiredFittedReferenceMismatch")
    assert pcb_required_fitted_reference_models.PcbRequiredFittedReferenceMap.__module__.endswith(
        "pcb_required_fitted_reference_models"
    )

    tree = ast.parse(predicate_path.read_text(encoding="utf-8"), filename=predicate_path.name)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "compare_required_fitted_references" in functions


def test_required_fitted_rule_catalog_points_to_its_predicate_owner() -> None:
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "pcb.required_fitted_reference"
    )

    assert rule.theme == "pcb"
    assert rule.default_mode == "block"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/pcb_required_fitted_reference_checks.py#"
        "compare_required_fitted_references"
    )
    assert rule.implementation_owner in rule.implementation_refs
