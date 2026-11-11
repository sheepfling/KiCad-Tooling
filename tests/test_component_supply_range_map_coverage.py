"""Review fitted IC power inputs missing from the authored range map."""

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
from kicad_tooling.hwrepo.design_lint_power_supply_range_map_coverage import (
    component_supply_range_map_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract
from kicad_tooling.hwrepo.power_component_supply_range_map_coverage import (
    component_supply_range_map_coverage_issues,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.component_supply_voltage_ranges import (
    SUPPLY_FOOTPRINT,
    SUPPLY_SYMBOL,
    supply_range_map,
    supply_range_map_coverage_complete_map,
    supply_range_map_coverage_netlist,
    supply_range_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID: DesignLintRuleId = "power.component_supply_range_map_coverage"


def review_policy(requirements: ComponentSupplyVoltageRangeMap) -> DesignLintPolicy:
    """Return the explicit opt-in used by the synthetic coverage case."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="The synthetic regression explicitly checks range-map coverage",
            ),
        ),
        component_supply_voltage_range_map=requirements,
    )


def test_unmapped_fitted_ic_supply_pins_need_review() -> None:
    issues = component_supply_range_map_coverage_issues(
        supply_range_map_coverage_netlist(), supply_range_map()
    )
    findings = component_supply_range_map_coverage_candidates(
        supply_range_map_coverage_netlist(), supply_range_map()
    )

    assert len(issues) == len(findings) == 1
    assert issues[0].reference == "U3"
    assert issues[0].native_power_input_pins == ("U3.1", "U3.2")
    assert findings[0].rule_id == RULE_ID
    assert findings[0].evidence["component"] == ("U3",)
    assert findings[0].evidence["native_power_input_pins"] == ("U3.1", "U3.2")
    assert findings[0].evidence["map_sha256"] == (
        component_supply_voltage_range_map_sha256(supply_range_map()),
    )
    assert "does not infer voltage limits" in findings[0].message


def test_complete_current_map_quiets_each_supported_ic() -> None:
    assert (
        component_supply_range_map_coverage_issues(
            supply_range_map_coverage_netlist(), supply_range_map_coverage_complete_map()
        )
        == ()
    )


def test_stale_identity_does_not_count_as_current_map_coverage() -> None:
    stale_map = supply_range_map(
        supply_range_requirement(),
        supply_range_requirement(
            id="u3-stale-input",
            reference="U3",
            pin="U3.1",
            expected_symbol=SUPPLY_SYMBOL,
            expected_footprint=SUPPLY_FOOTPRINT,
            expected_part_id="STALE-SYNTHETIC-PART",
        ),
    )

    issues = component_supply_range_map_coverage_issues(
        supply_range_map_coverage_netlist(), stale_map
    )

    assert len(issues) == 1
    assert issues[0].reference == "U3"
    assert issues[0].stale_map_identity


def test_non_ic_dnp_and_non_power_input_components_are_not_candidates() -> None:
    observed = supply_range_map_coverage_netlist()
    netlist = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "Q1": ComponentContract(value="Synthetic transistor", footprint="Synthetic:Q"),
                "J1": ComponentContract(value="Synthetic connector", footprint="Synthetic:J"),
                "U4": ComponentContract(value="Synthetic passive IC", footprint="Synthetic:U"),
            },
            "component_symbols": {
                **observed.component_symbols,
                "U4": "Synthetic:NoSupplyPin",
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "Q1.1": "power_in",
                "J1.1": "power_in",
                "U4.1": "passive",
            },
            "dnp_components": ("U3",),
        }
    )

    assert component_supply_range_map_coverage_issues(netlist, supply_range_map()) == ()


def test_map_order_does_not_change_issue_identity_or_order() -> None:
    requirements = supply_range_map_coverage_complete_map().requirements
    forward = ComponentSupplyVoltageRangeMap(
        basis="Synthetic tooling regression only", requirements=requirements
    )
    reverse = ComponentSupplyVoltageRangeMap(
        basis="Synthetic tooling regression only", requirements=tuple(reversed(requirements))
    )

    assert component_supply_voltage_range_map_sha256(forward) == (
        component_supply_voltage_range_map_sha256(reverse)
    )
    assert component_supply_range_map_coverage_issues(
        supply_range_map_coverage_netlist(), forward
    ) == component_supply_range_map_coverage_issues(supply_range_map_coverage_netlist(), reverse)


def test_enabled_rule_requires_a_source_map() -> None:
    with pytest.raises(ValidationError, match="requires component_supply_voltage_range_map"):
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review missing component map coverage",
                ),
            )
        )


def test_enabled_rule_uses_shared_evaluator_and_can_be_disabled() -> None:
    observed = supply_range_map_coverage_netlist()
    report = evaluate(
        "synthetic-unmapped-supply-range", coach(observed), review_policy(supply_range_map())
    )
    disabled = evaluate(
        "synthetic-disabled-supply-range",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="This project does not opt into supply range coverage review",
                ),
            ),
            component_supply_voltage_range_map=supply_range_map(),
        ),
    )

    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["native_power_input_pins"] == ("U3.1", "U3.2")
    disabled_findings = tuple(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert len(disabled_findings) == 1
    assert disabled_findings[0].mode == "off"
    assert disabled_findings[0].disposition == "RULE_OFF"


def test_map_coverage_rule_is_default_off() -> None:
    report = evaluate(
        "synthetic-default-supply-range-policy",
        coach(supply_range_map_coverage_netlist()),
        DesignLintPolicy(component_supply_voltage_range_map=supply_range_map()),
    )

    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].mode == "off"
    assert findings[0].disposition == "RULE_OFF"
