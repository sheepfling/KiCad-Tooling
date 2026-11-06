"""Keep custom DRC source-rule selectors focused on their own tests."""

from __future__ import annotations

import pytest

from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.architecture,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
]

RULE_NODE_CASES = (
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_pcb_dru_conflicting_severities.py::test_conflicting_direct_severities_request_source_bound_review",
    ),
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_design_lint_mcp_parity_pcb_dru_conflicting_severities.py::test_conflicting_custom_drc_severity_review_matches_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_pcb_dru_conflicting_severities_native.py::test_multiple_and_single_severity_rules_reach_native_sentinel",
    ),
)


def test_conflicting_severity_selector_collects_only_registered_rule_tests() -> None:
    rule_ids = tuple(sorted({rule_id for rule_id, _ in RULE_NODE_CASES}))
    result = collect_rule_nodes(rule_ids)

    assert result.returncode == 0, result.stdout + result.stderr
    for _, expected_node in RULE_NODE_CASES:
        assert expected_node in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout
