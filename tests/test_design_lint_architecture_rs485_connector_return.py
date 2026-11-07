"""Guard the RS-485 return-review owner and shared return-role predicate."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

RULE_ID = "connector.rs485_pair_without_return_review"
OWNER = "kicad_tooling/hwrepo/connector_return_rs485_review.py#rs485_connector_missing_return_candidates"
MODULES = (
    "connector_return_rs485_review.py",
    "connector_return_pins.py",
    "design_lint_return_domain_candidates.py",
    "rs485_generic_connector_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_has_a_return_theme_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "returns"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_and_protocol_modules_stay_below_the_architecture_limit() -> None:
    sizes = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(size < 500 for size in sizes.values()), sizes


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_dispatcher_delegates_to_the_rs485_owner() -> None:
    module = HWREPO / "design_lint_return_domain_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "rs485_connector_missing_return_candidates" in calls


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_protocol_return_rules_share_the_canonical_return_role_predicate() -> None:
    modules = (
        "connector_return_serial_review.py",
        "connector_return_i2c_review.py",
        "connector_return_can_review.py",
        "connector_return_rs485_review.py",
    )
    for name in modules:
        tree = ast.parse((HWREPO / name).read_text(encoding="utf-8"), filename=name)
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "connector_return_pins"
            and any(alias.name == "connector_pin_group_has_return_role" for alias in node.names)
            for node in tree.body
        ), name
