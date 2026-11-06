"""Guard the typed source route for repeated component return-pin findings."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as compatibility_models
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

RULE_ID = "component.repeated_return_pin_function"
PREDICATE_OWNER = (
    "kicad_tooling/hwrepo/component_return_pin_domains.py#component_return_pin_net_divergences"
)
EVIDENCE_OWNER = "kicad_tooling/hwrepo/design_lint_component_return_candidate_evidence.py"


def test_catalog_and_predicate_use_the_returns_theme_evidence_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    predicate_path = REPO_ROOT / "kicad_tooling/hwrepo/component_return_pin_domains.py"
    evidence_path = REPO_ROOT / EVIDENCE_OWNER
    predicate_tree = ast.parse(predicate_path.read_text(encoding="utf-8"))
    evidence_tree = ast.parse(evidence_path.read_text(encoding="utf-8"))
    refs = set(rule.implementation_refs)

    assert rule.implementation_owner == PREDICATE_OWNER
    assert PREDICATE_OWNER in refs
    assert f"{EVIDENCE_OWNER}#project_component_return_pin_evidence" in refs
    assert f"{EVIDENCE_OWNER}#component_return_pin_candidate" in refs
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "component_return_pin_candidate"
        for node in ast.walk(predicate_tree)
    )
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_types"
        and any(alias.name == "Candidate" for alias in node.names)
        for node in ast.walk(predicate_tree)
    )
    assert {
        node.name
        for node in evidence_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    } >= {
        "ComponentReturnPinObservation",
        "ComponentReturnPinFindingEvidence",
        "ComponentReturnPinCandidate",
        "project_component_return_pin_evidence",
        "component_return_pin_candidate",
    }


def test_component_return_evidence_types_stay_private_to_the_theme_owner() -> None:
    assert line_count(REPO_ROOT / EVIDENCE_OWNER) < IMPLEMENTATION_MAX_LINES
    assert not hasattr(compatibility_models, "ComponentReturnPinFindingEvidence")
    assert not hasattr(compatibility_models, "ComponentReturnPinCandidate")
