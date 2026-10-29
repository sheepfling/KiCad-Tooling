"""Keep the PCB signal-path rule tag tied to its exact-native DRC cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]


def test_pcb_signal_path_rule_selects_native_fault_control_case() -> None:
    rule = next(
        entry for entry in rule_catalog().rules if entry.rule_id == "pcb.signal_path_rule_coverage"
    )
    native_fixture = "KICAD_RUN_NATIVE_PCB_FIXTURES"
    native_test = (
        "tests.test_pcb_signal_path_native."
        "test_native_signal_path_drc_faults_are_repeatable"
    )

    assert native_fixture in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
