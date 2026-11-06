"""Keep the generic RS-485 connector lint in its focused interface modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.rs485_generic_connector_pair_review"
MODULES = (
    "rs485_generic_connector_models.py",
    "rs485_generic_connector_candidates.py",
    "design_lint_rs485_generic_connector_candidates.py",
    "design_lint_rs485_generic_connector_candidate_evidence.py",
    "design_lint_rs485_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_predicate_has_a_protocol_owned_implementation() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/rs485_generic_connector_candidates.py#rs485_generic_connector_pairs"
    )
    assert rule.implementation_owner in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_modules_stay_below_review_limit() -> None:
    package = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
    counts = {
        name: len((package / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rs485_theme_coordinator_routes_the_typed_connector_coverage() -> None:
    module = Path(__file__).parents[1] / "kicad_tooling/hwrepo/design_lint_rs485_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "rs485_generic_connector_pair_review_candidates" in calls
