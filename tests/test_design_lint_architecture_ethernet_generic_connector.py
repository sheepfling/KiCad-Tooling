"""Keep Ethernet generic-connector review in focused interface modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.ethernet_generic_connector_pair_review"
OWNER = "kicad_tooling/hwrepo/bus_ethernet_generic_connector.py#generic_ethernet_connector_pairs"
MODULES = (
    "bus_ethernet_generic_connector.py",
    "ethernet_generic_connector_models.py",
    "design_lint_ethernet_generic_connector_candidate_evidence.py",
    "design_lint_ethernet_generic_connector_candidates.py",
    "design_lint_bus_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_owner_and_protocol_candidate_dispatch_are_theme_owned() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs

    module = Path(__file__).parents[1] / "kicad_tooling/hwrepo/design_lint_bus_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "ethernet_generic_connector_pair_review_candidates" in calls


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ethernet_generic_connector_modules_stay_below_review_limit() -> None:
    package = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
    counts = {
        name: len((package / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts
