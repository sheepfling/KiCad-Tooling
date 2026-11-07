"""Focused pytest selectors for capacitor hold-up fault/control coverage."""

from __future__ import annotations

import pytest

from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint, pytest.mark.architecture]

RULE_ID = "power.capacitor_hold_up_below_project_minimum"
EXPECTED_NODES = (
    "tests/test_capacitor_hold_up.py::test_nominal_hold_up_below_authored_requirement_is_reviewed",
    "tests/test_capacitor_hold_up.py::test_parallel_bank_below_limit_reports_total_and_each_mapped_member",
    "tests/test_capacitor_hold_up_parity.py::test_project_authored_parallel_bank_hold_up_matches_cli_and_mcp",
    "tests/test_capacitor_hold_up_native_fixture.py::test_native_parallel_capacitor_bank_fault_and_control_are_source_bound",
)


def test_parallel_bank_selector_collects_fault_parity_and_native_controls() -> None:
    result = collect_rule_nodes(RULE_ID)
    assert result.returncode == 0, result.stdout + result.stderr
    for expected_node in EXPECTED_NODES:
        assert expected_node in result.stdout
