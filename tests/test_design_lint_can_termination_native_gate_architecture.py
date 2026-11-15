"""Guard native fixture registration for the CAN termination review rules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

_CAN_TERMINATION_NATIVE_CASES = (
    pytest.param("bus.can_missing_termination", id="can-missing-termination"),
    pytest.param("bus.can_excess_termination", id="can-excess-termination"),
    pytest.param("bus.can_single_local_termination", id="can-single-local-termination"),
)


@pytest.mark.parametrize("rule_id", _CAN_TERMINATION_NATIVE_CASES)
def test_can_termination_rules_select_the_native_fault_control_lane(rule_id: str) -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)

    assert "KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES" in rule.required_native_fixtures
    native_test = (
        "tests.test_can_native_fixture_lanes."
        "test_native_can_termination_heuristics_fault_and_control"
    )
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
