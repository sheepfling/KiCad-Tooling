"""Keep SWD connector-return review in its dedicated return-theme owner."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

RULE_ID = "connector.swd_pair_without_return_review"
OWNER = (
    "kicad_tooling/hwrepo/connector_return_swd_review.py#swd_connector_missing_return_candidates"
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_swd_return_rule_has_a_focused_return_theme_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    module = HWREPO / "connector_return_swd_review.py"

    assert line_count(module) < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "returns"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_dispatcher_delegates_to_the_swd_owner() -> None:
    module = HWREPO / "design_lint_return_domain_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "swd_connector_missing_return_candidates" in calls
    assert "SwdConnectorReturnCandidate" not in calls
