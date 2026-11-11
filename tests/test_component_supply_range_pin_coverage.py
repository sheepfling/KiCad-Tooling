"""Regressions for complete mapped IC supply-range pin coverage."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    component_supply_voltage_range_map_sha256,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_power_supply_range_coverage import (
    component_supply_range_pin_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.power_component_supply_range_coverage import (
    component_supply_range_pin_coverage_issues,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.component_supply_voltage_ranges import (
    supply_range_map,
    supply_range_netlist,
    supply_range_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID: DesignLintRuleId = "power.component_supply_range_pin_coverage"


def complete_supply_range_map() -> ComponentSupplyVoltageRangeMap:
    """Map both native power-input pins in the synthetic L7805 inventory."""
    return supply_range_map(
        supply_range_requirement(),
        supply_range_requirement(
            id="u1-ground-input",
            pin="U1.2",
            expected_pin_function="GND",
            minimum_voltage_v=0.0,
            maximum_voltage_v=0.0,
        ),
    )


def review_policy(requirements: ComponentSupplyVoltageRangeMap) -> DesignLintPolicy:
    """Return the explicit opt-in used by the test-owned map."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="The synthetic regression explicitly checks mapped pin coverage",
            ),
        ),
        component_supply_voltage_range_map=requirements,
    )


def test_unmapped_power_input_pin_needs_review() -> None:
    findings = component_supply_range_pin_coverage_candidates(
        supply_range_netlist(), supply_range_map()
    )

    assert len(findings) == 1
    assert findings[0].rule_id == RULE_ID
    assert findings[0].evidence["native_power_input_pins"] == ("U1.1", "U1.2")
    assert findings[0].evidence["mapped_range_pins"] == ("U1.1",)
    assert findings[0].evidence["unmapped_power_input_pins"] == ("U1.2",)
    assert "does not verify the symbol against the physical package" in findings[0].message


def test_complete_component_supply_pin_map_is_quiet() -> None:
    assert (
        component_supply_range_pin_coverage_issues(
            supply_range_netlist(), complete_supply_range_map()
        )
        == ()
    )


def test_non_power_input_pin_does_not_require_range_entry() -> None:
    netlist = supply_range_netlist().model_copy(
        update={
            "pin_electrical_types": {
                "U1.1": "power_in",
                "U1.2": "passive",
                "U1.3": "power_out",
            }
        }
    )

    assert component_supply_range_pin_coverage_issues(netlist, supply_range_map()) == ()


def test_unmapped_pin_without_native_electrical_type_keeps_coverage_incomplete() -> None:
    netlist = supply_range_netlist().model_copy(
        update={"pin_electrical_types": {"U1.1": "power_in", "U1.3": "power_out"}}
    )
    issues = component_supply_range_pin_coverage_issues(netlist, supply_range_map())

    assert len(issues) == 1
    assert issues[0].pin_type_unavailable_pins == ("U1.2",)
    assert issues[0].unmapped_power_input_pins == ()


def test_missing_native_pin_inventory_keeps_coverage_incomplete() -> None:
    netlist = supply_range_netlist().model_copy(update={"component_pin_numbers": {}})
    issues = component_supply_range_pin_coverage_issues(netlist, supply_range_map())

    assert len(issues) == 1
    assert issues[0].pin_inventory_unavailable


def test_native_typed_pin_outside_inventory_needs_review() -> None:
    netlist = supply_range_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "3")}}
    )
    issues = component_supply_range_pin_coverage_issues(netlist, supply_range_map())

    assert len(issues) == 1
    assert issues[0].native_power_input_pins == ("U1.1", "U1.2")
    assert issues[0].pin_inventory_disagreement_pins == ("U1.2",)


def test_requirement_entries_for_one_component_must_share_identity() -> None:
    with pytest.raises(ValidationError, match="consistent identity"):
        supply_range_map(
            supply_range_requirement(),
            supply_range_requirement(
                id="u1-ground-input",
                pin="U1.2",
                expected_pin_function="GND",
                minimum_voltage_v=0.0,
                maximum_voltage_v=0.0,
                expected_part_id="DIFFERENT-SYNTHETIC-PART",
            ),
        )


def test_stale_component_identity_is_left_to_the_exact_range_rule() -> None:
    netlist = supply_range_netlist(part_id="DIFFERENT-SYNTHETIC-PART")

    assert component_supply_range_pin_coverage_issues(netlist, supply_range_map()) == ()


def test_requirement_order_does_not_change_coverage_evidence() -> None:
    mapped_input = supply_range_requirement()
    mapped_ground = supply_range_requirement(
        id="u1-ground-input",
        pin="U1.2",
        expected_pin_function="GND",
        minimum_voltage_v=0.0,
        maximum_voltage_v=0.0,
    )
    first = supply_range_map(mapped_input, mapped_ground)
    second = supply_range_map(mapped_ground, mapped_input)
    forward = component_supply_range_pin_coverage_issues(supply_range_netlist(), first)
    reverse = component_supply_range_pin_coverage_issues(supply_range_netlist(), second)

    assert component_supply_voltage_range_map_sha256(first) == (
        component_supply_voltage_range_map_sha256(second)
    )
    assert forward == reverse == ()


def test_enabled_rule_requires_the_project_authored_range_map() -> None:
    with pytest.raises(ValidationError, match="requires component_supply_voltage_range_map"):
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review mapped power-pin coverage",
                ),
            )
        )


def test_enabled_rule_runs_through_the_shared_design_lint_evaluator() -> None:
    report = evaluate(
        "synthetic-supply-range-coverage",
        coach(supply_range_netlist()),
        review_policy(supply_range_map()),
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].disposition == "OPEN"
    assert findings[0].evidence["unmapped_power_input_pins"] == ("U1.2",)


def test_complete_project_authored_map_clears_the_coverage_review() -> None:
    report = evaluate(
        "synthetic-complete-supply-range-coverage",
        coach(supply_range_netlist()),
        review_policy(complete_supply_range_map()),
    )

    assert RULE_ID not in {item.rule_id for item in report.findings}
