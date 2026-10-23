"""Keep component rule catalog tags connected to native fixture lanes."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
]


def test_oscillator_output_path_rule_selects_its_native_fault_control_lane() -> None:
    rule_id = "oscillator.output_load_path_mismatch"
    native_switch = "KICAD_RUN_NATIVE_OSCILLATOR_OUTPUT_PATH_FIXTURES"
    native_test = (
        "tests.test_oscillator_output_paths_native_fixture_lane."
        "test_native_oscillator_output_path_fault_and_control_are_version_pinned_and_repeatable"
    )
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)

    assert set(rule.supported_kicad_versions) == {"10.0.0", "10.0.5"}
    assert native_switch in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures


def test_polarized_capacitor_rule_selects_its_exact_native_fault_control_lane() -> None:
    rule_id = "component.polarized_capacitor_reversed_on_named_rails"
    native_switch = "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES"
    native_test = (
        "tests.test_polarized_capacitor_native_fixture."
        "test_native_polarized_capacitor_fault_and_control_are_deterministic"
    )
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)

    assert set(rule.supported_kicad_versions) == {"10.0.0", "10.0.5"}
    assert native_switch in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
