"""Review-only lint for named supply pins on explicitly negative rail labels."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.power_rails import negative_voltage_rail_key
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.power_pin_net_roles import supply_pin_on_rail_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint, pytest.mark.component_lint]

RULE_ID = "power.named_supply_pin_on_negative_rail"


def _report(rail: str, *, function: str = "VDD", **options: object):
    observed = supply_pin_on_rail_netlist(rail, function=function, **options)
    return evaluate("synthetic-negative-supply-rail", coach(observed), DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_supply_pin_on_negative_rail_is_reviewed() -> None:
    report = _report("-5V")

    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "U1.1: VDD pin assigned to -5V"
    assert findings[0].evidence == {
        "U1.1": ("native_function=VDD", "supply_function_key=vdd"),
        "assigned_net": ("-5V",),
        "negative_rail_key": ("5V",),
    }
    assert "do not prove electrical potential" in findings[0].message
    assert "power.pin_function_net_role_conflict" not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("name", "expected"),
    (
        ("-5V", "5V"),
        ("-5.0V", "5V"),
        ("-3V3", "3V3"),
        ("-3.3V", "3V3"),
        ("- 3.3 V", "3V3"),
        ("-1V8", "1V8"),
        ("-2.5V", "2V5"),
        ("-48V", "48V"),
        ("+5V", None),
        ("VEE", None),
        ("--5V", None),
        ("-5V_AUX", None),
        ("NEG_5V", None),
    ),
)
def test_negative_rail_name_recognition_is_narrow(name: str, expected: str | None) -> None:
    assert negative_voltage_rail_key(name) == expected


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("rail", "function", "options"),
    (
        ("+5V", "VDD", {}),
        ("-5V", "VEE", {}),
        ("-5V", "GND", {}),
        ("-5V", "VDD", {"dnp": True}),
        ("-5V", "VDD", {"assigned": False}),
        ("-5V", "VDD", {"ambiguous": True}),
        ("-CUSTOM", "VDD", {}),
    ),
)
def test_unrecognized_negative_roles_and_nonunique_assignments_are_controls(
    rail: str,
    function: str,
    options: dict[str, object],
) -> None:
    report = evaluate(
        "synthetic-negative-supply-rail-control",
        coach(supply_pin_on_rail_netlist(rail, function=function, **options)),
        DesignLintPolicy(),
    )

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_negative_rail_review_supports_policy_and_exact_ignore() -> None:
    baseline = _report("-5V")
    finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    source = supply_pin_on_rail_netlist("-5V")
    blocked = evaluate(
        "synthetic-negative-supply-rail",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project explicitly gates this review",
                ),
            )
        ),
    )
    disabled = evaluate(
        "synthetic-negative-supply-rail",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project does not use negative named rails",
                ),
            )
        ),
    )
    ignored = evaluate(
        "synthetic-negative-supply-rail",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed exception",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert ignored.status == "PASS"
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_assignment_correction_clears_the_negative_rail_candidate() -> None:
    fault = supply_pin_on_rail_netlist("-5V")
    corrected = supply_pin_on_rail_netlist("+5V")
    fault_report = evaluate("synthetic-negative-supply-rail", coach(fault), DesignLintPolicy())
    corrected_report = evaluate(
        "synthetic-negative-supply-rail", coach(corrected), DesignLintPolicy()
    )

    assert [item.rule_id for item in fault_report.findings].count(RULE_ID) == 1
    assert RULE_ID not in {item.rule_id for item in corrected_report.findings}
