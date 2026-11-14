"""Keep mapped SPI connector return review in bounded return-theme modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

RULE_ID = "connector.spi_triad_without_return_review"
OWNER = (
    "kicad_tooling/hwrepo/connector_return_spi_review.py#spi_connector_missing_return_candidates"
)
MODULES = (
    "connector_return_spi_review.py",
    "spi_generic_connector_candidates.py",
    "connector_coverage.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_has_a_return_theme_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "returns"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_spi_return_modules_stay_below_review_limit() -> None:
    sizes = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(size < 500 for size in sizes.values()), sizes


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connector_coordinator_delegates_to_the_return_owner() -> None:
    module = HWREPO / "design_lint_connector_candidate_dispatch.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "connector_candidates"
    )
    calls = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "spi_connector_missing_return_candidates" in calls
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"Candidate", "SpiConnectorReturnCandidate"}
        for node in ast.walk(function)
    )
