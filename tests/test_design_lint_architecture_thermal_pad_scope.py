"""Guard ownership and limits for the explicit thermal-pad scope prompt."""

from __future__ import annotations

import ast
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    design_lint_pcb_thermal_pad_scope,
    design_lint_pcb_thermal_pad_scope_evidence,
)
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.design_lint_pcb_inputs import PcbCandidateInputs
from kicad_tooling.hwrepo.design_lint_pcb_thermal_pad_scope_evidence import (
    PcbExplicitThermalPadScopeCandidate,
    PcbExplicitThermalPadScopeEvidence,
)
from kicad_tooling.hwrepo.pcb_thermal_via_models import PcbThermalViaMap
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]

RULE_ID = "pcb.explicit_thermal_pad_scope_unreviewed"
OWNER = (
    "kicad_tooling/hwrepo/design_lint_pcb_thermal_pad_scope.py#"
    "explicit_thermal_pad_scope_candidates"
)
EVIDENCE_OWNER = (
    "kicad_tooling/hwrepo/design_lint_pcb_thermal_pad_scope_evidence.py#"
    "project_explicit_thermal_pad_scope_evidence"
)


def test_rule_catalog_names_the_theme_owned_prompt_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path = HWREPO / "design_lint_pcb_thermal_pad_scope.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))

    assert rule.theme == "pcb"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert EVIDENCE_OWNER in rule.implementation_refs
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "explicit_thermal_pad_scope_candidates"
        for node in owner_tree.body
    )
    assert any("does not assert" in item for item in rule.limitations)


def test_candidate_keeps_typed_source_and_theme_owned_projection() -> None:
    source_type = get_type_hints(PcbExplicitThermalPadScopeCandidate)["source_evidence"]
    assert source_type is PcbExplicitThermalPadScopeEvidence
    assert (
        design_lint_pcb_thermal_pad_scope_evidence.project_explicit_thermal_pad_scope_evidence.__module__
        == design_lint_pcb_thermal_pad_scope_evidence.__name__
    )


def test_thermal_map_is_carried_on_the_pcb_candidate_input_group() -> None:
    fields = get_type_hints(PcbCandidateInputs)
    assert fields["thermal_via_map"] == PcbThermalViaMap | None
    assert fields["is_pcb_project"] is bool


def test_theme_owner_and_regression_suites_stay_below_review_limits() -> None:
    files = (
        HWREPO / "design_lint_pcb_thermal_pad_scope.py",
        HWREPO / "design_lint_pcb_thermal_pad_scope_evidence.py",
        HWREPO / "design_lint_candidate_aggregation.py",
        HWREPO / "design_lint_pcb_inputs.py",
        HWREPO / "design_lint_evaluation_preparation.py",
    )
    sizes = {path.name: line_count(path) for path in files}
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
    assert line_count(HWREPO.parent.parent / "tests/test_pcb_thermal_pad_scope.py") < 500


def test_review_rule_keeps_native_and_synthetic_fixture_boundaries_declared() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert "KICAD_RUN_NATIVE_THERMAL_PAD_SCOPE" in rule.required_native_fixtures
    assert any("_native." in item for item in rule.fault_fixtures)
    assert any("_native." in item for item in rule.valid_control_fixtures)
    assert (
        design_lint_pcb_thermal_pad_scope.explicit_thermal_pad_scope_candidates.__module__
        == design_lint_pcb_thermal_pad_scope.__name__
    )
