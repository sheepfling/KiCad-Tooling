"""Keep the generic UART connector review in focused theme modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.serial_generic_connector_pair_review"
MODULES = (
    "serial_generic_connector_models.py",
    "serial_generic_connector_candidates.py",
    "design_lint_serial_generic_connector_candidates.py",
    "design_lint_serial_generic_connector_candidate_evidence.py",
    "design_lint_serial_bus_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_predicate_has_a_serial_owned_implementation() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/serial_generic_connector_candidates.py#serial_generic_connector_pairs"
    )
    assert rule.implementation_owner in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_serial_generic_connector_modules_stay_below_review_limit() -> None:
    counts = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_serial_protocol_coordinator_preserves_the_legacy_serial_candidates() -> None:
    module = HWREPO / "design_lint_serial_bus_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert calls == {
        "serial_signal_candidates",
        "serial_generic_connector_pair_review_candidates",
    }
