"""Guard ownership and source-evidence boundaries for numeric connector peers."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_numeric_peer_open_rule_has_one_small_connector_owned_predicate() -> None:
    module_path = HWREPO / "connector_numeric_peer_open_outliers.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=module_path.name)
    predicate_names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "generic_numeric_connector_peer_pin_open_outliers"
    }
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.generic_peer_pin_open_outlier"
    )

    assert line_count(module_path) < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "connector_numeric_peer_open_evidence.py") < IMPLEMENTATION_MAX_LINES
    assert predicate_names == {"generic_numeric_connector_peer_pin_open_outliers"}
    assert rule.theme == "connectors"
    assert rule.default_mode == "review"
    assert rule.implementation_owner in rule.implementation_refs
    assert rule.implementation_owner.endswith(
        "connector_numeric_peer_open_outliers.py#generic_numeric_connector_peer_pin_open_outliers"
    )
    assert any(
        "connector_numeric_peer_open_evidence.py#project_connector_numeric_peer_open_evidence"
        in item
        for item in rule.implementation_refs
    )
