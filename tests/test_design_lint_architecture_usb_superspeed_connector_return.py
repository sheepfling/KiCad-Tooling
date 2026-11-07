"""Guard USB SuperSpeed connector-return rule ownership and shared evidence."""

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

RULE_ID = "connector.usb_superspeed_pair_without_return_review"
OWNER = (
    "kicad_tooling/hwrepo/connector_return_usb_superspeed_review.py#"
    "usb_superspeed_connector_missing_return_candidates"
)
MODULES = (
    "connector_return_usb_superspeed_review.py",
    "connector_return_usb2_review.py",
    "connector_return_pins.py",
    "connector_coverage.py",
    "usb_peer_endpoint_analysis.py",
    "design_lint_return_domain_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_has_a_return_theme_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "returns"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_return_modules_stay_below_the_architecture_limit() -> None:
    sizes = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(size < 500 for size in sizes.values()), sizes


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_dispatcher_delegates_to_both_usb_pair_owners() -> None:
    module = HWREPO / "design_lint_return_domain_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "usb2_connector_missing_return_candidates" in calls
    assert "usb_superspeed_connector_missing_return_candidates" in calls


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_superspeed_owner_uses_shared_endpoint_and_return_role_services() -> None:
    module = HWREPO / "connector_return_usb_superspeed_review.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    imports = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert ("usb_peer_endpoint_analysis", "usb_superspeed_endpoints") in imports
    assert ("connector_return_pins", "connector_pin_group_has_return_role") in imports
    assert ("connector_return_pins", "connector_pin_for_assigned_net") in imports
