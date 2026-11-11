"""Project-mapped exact IC supply-pin operating-range review."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    component_supply_voltage_range_map_sha256,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_power_supply_range import (
    component_supply_voltage_range_candidates,
)
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.power_component_supply_range import (
    component_supply_voltage_range_issues,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.component_supply_voltage_ranges import (
    supply_range_map,
    supply_range_netlist,
    supply_range_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID: DesignLintRuleId = "power.component_supply_voltage_outside_range"


def test_supported_positive_voltage_label_below_range_needs_review() -> None:
    findings = component_supply_voltage_range_candidates(
        supply_range_netlist(input_net="3V3"), supply_range_map()
    )

    assert len(findings) == 1
    assert findings[0].rule_id == RULE_ID
    assert findings[0].evidence["pin"] == ("U1.1",)
    assert findings[0].evidence["assigned_net"] == ("3V3",)
    assert findings[0].evidence["net_label_voltage_v"] == ("3.3",)
    assert "outside the reviewed inclusive range" in findings[0].evidence["issues"][0]


def test_supported_positive_voltage_inside_inclusive_range_is_quiet() -> None:
    findings = component_supply_voltage_range_issues(
        supply_range_netlist(input_net="12V"),
        supply_range_map(supply_range_requirement(minimum_voltage_v=12.0, maximum_voltage_v=35.0)),
    )

    assert findings == ()


def test_exact_range_boundary_is_quiet_and_upper_outlier_is_reported() -> None:
    requirement = supply_range_requirement(minimum_voltage_v=12.0, maximum_voltage_v=12.0)
    in_range = component_supply_voltage_range_issues(
        supply_range_netlist(input_net="12V"), supply_range_map(requirement)
    )
    out_of_range = component_supply_voltage_range_issues(
        supply_range_netlist(input_net="24V"), supply_range_map(requirement)
    )

    assert in_range == ()
    assert len(out_of_range) == 1
    assert out_of_range[0].actual_voltage_v is not None
    assert out_of_range[0].actual_voltage_v == Decimal(24)


@pytest.mark.parametrize(
    "netlist, expected_issue",
    (
        (supply_range_netlist(input_net=None), "U1.1 is unassigned"),
        (
            supply_range_netlist(input_net="VIN"),
            "no supported explicit nominal-voltage label",
        ),
        (
            supply_range_netlist(part_id="OTHER-SYNTHETIC-PART"),
            "PART_ID is OTHER-SYNTHETIC-PART",
        ),
        (supply_range_netlist(dnp=True), "U1 is marked DNP"),
        (
            supply_range_netlist(pin_electrical_type="passive"),
            "pin electrical type is passive; expected power_in",
        ),
        (
            supply_range_netlist(pin_function="VCC"),
            "pin function is VCC; expected IN",
        ),
    ),
)
def test_missing_or_stale_mapping_evidence_needs_review(netlist, expected_issue: str) -> None:
    findings = component_supply_voltage_range_issues(netlist, supply_range_map())

    assert len(findings) == 1
    assert any(expected_issue in issue for issue in findings[0].issues)


def test_requirement_order_does_not_change_map_digest_or_issue_order() -> None:
    first = supply_range_requirement(id="u1-input", pin="U1.1")
    second = first.model_copy(
        update={"id": "u1-output-mismatch", "pin": "U1.3", "expected_pin_function": "OUT"}
    )
    forward = supply_range_map(first, second)
    reverse = supply_range_map(second, first)

    assert component_supply_voltage_range_map_sha256(forward) == (
        component_supply_voltage_range_map_sha256(reverse)
    )
    assert component_supply_voltage_range_issue_pins(forward) == (
        component_supply_voltage_range_issue_pins(reverse)
    )


def component_supply_voltage_range_issue_pins(requirements: ComponentSupplyVoltageRangeMap):
    """Project only stable pin and requirement keys from the fixture scan."""
    issues = component_supply_voltage_range_issues(supply_range_netlist(), requirements)
    return tuple((item.requirement.id, item.requirement.pin) for item in issues)


def test_enabled_rule_requires_an_authored_map() -> None:
    from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy

    with pytest.raises(ValidationError, match="requires component_supply_voltage_range_map"):
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review exact supply-pin voltage ranges",
                ),
            )
        )


def test_enabled_rule_runs_through_the_shared_design_lint_evaluator() -> None:
    from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy

    requirement_map = supply_range_map()
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Review exact supply-pin voltage ranges",
            ),
        ),
        component_supply_voltage_range_map=requirement_map,
    )
    report = evaluate("synthetic-supply-range", coach(supply_range_netlist()), policy)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].disposition == "OPEN"
    assert findings[0].evidence["net_label_voltage_v"] == ("3.3",)


def test_enabled_rule_clears_when_the_native_net_label_moves_inside_authored_range() -> None:
    from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy

    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Review exact supply-pin voltage ranges",
            ),
        ),
        component_supply_voltage_range_map=supply_range_map(),
    )
    report = evaluate(
        "synthetic-supply-range-control", coach(supply_range_netlist(input_net="12V")), policy
    )

    assert RULE_ID not in {item.rule_id for item in report.findings}
