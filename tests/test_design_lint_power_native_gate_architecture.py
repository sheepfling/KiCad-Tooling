"""Keep power-path rule tags connected to exact-native fault/control cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
]

_POWER_PATH_NATIVE_CASES = (
    pytest.param(
        "power.input_without_supported_source_path",
        id="unmapped-source-path-heuristic",
    ),
    pytest.param(
        "power.mapped_series_path_mismatch",
        id="mapped-series-path-contract",
    ),
)


@pytest.mark.parametrize(("rule_id",), _POWER_PATH_NATIVE_CASES)
def test_power_path_rule_tags_select_native_fault_control_case(rule_id: str) -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)
    native_fixture = "KICAD_RUN_NATIVE_POWER_PATH_FIXTURES"
    native_test = (
        "tests.test_power_path_native_fixture_lane."
        "test_mapped_ferrite_path_control_and_wrong_rail_fault"
    )

    assert native_fixture in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
