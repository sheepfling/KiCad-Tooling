"""Pinned native exports for synthetic thermocouple fault and control fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_two_pin_components import (
    TWO_PIN_COMPONENT_CANDIDATE_KINDS,
    two_pin_component_fixture_cases_for_rules,
)
from tests.design_lint_fixtures.two_pin_component_native import run_native_two_pin_rule_fixture

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.two_pin_thermocouple_same_net"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_thermocouple_native_fixture_scope_contains_all_exact_symbol_faults_and_controls() -> None:
    selected = two_pin_component_fixture_cases_for_rules((RULE_ID,))
    assert set(selected) == {"same-net-thermocouples", "distinct-nets-thermocouples"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {RULE_ID}
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS[RULE_ID] == frozenset({"thermocouple"})
    fault = selected["same-net-thermocouples"][2]
    assert fault == {
        "TC1: both thermocouple leads share TC1_TIED",
        "TC2: both thermocouple leads share TC2_TIED",
        "TC3: both thermocouple leads share TC3_TIED",
    }
    assert selected["distinct-nets-thermocouples"][2] == set()


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_thermocouple_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id=RULE_ID,
    )
