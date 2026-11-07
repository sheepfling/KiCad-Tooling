"""Keep JTAG connector return review in a focused returns-theme owner."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.design_lint_rule_selector_support import collect_rule_nodes
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

RULE_ID = "connector.jtag_pair_without_return_review"
OWNER = (
    "kicad_tooling/hwrepo/connector_return_jtag_review.py#jtag_connector_missing_return_candidates"
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_jtag_return_rule_has_a_focused_return_theme_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    module = HWREPO / "connector_return_jtag_review.py"

    assert line_count(module) < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "returns"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_dispatcher_delegates_to_the_jtag_owner() -> None:
    module = HWREPO / "design_lint_return_domain_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "jtag_connector_missing_return_candidates" in calls
    assert "JtagConnectorReturnCandidate" not in calls


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_selector_collects_fault_parity_architecture_and_native_cases() -> None:
    result = collect_rule_nodes(RULE_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "tests/test_jtag_connector_return_review.py::"
        "test_generic_contacts_on_jtag_pair_without_return_emit_review"
    ) in result.stdout
    assert (
        "tests/test_design_lint_mcp_parity_jtag_connector_return.py::"
        "test_jtag_connector_return_review_cli_mcp_parity"
    ) in result.stdout
    assert (
        "tests/test_jtag_connector_return_native_fixture_lane.py::"
        "test_native_jtag_connector_return_fault_and_control_repeat"
    ) in result.stdout
