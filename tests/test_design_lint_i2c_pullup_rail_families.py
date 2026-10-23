"""Focused synthetic regressions for the i2c lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    i2c_netlist_with_pullup_rails,
    policy_without_i2c_map_prompt,
)
from tests.design_lint_fixtures.i2c_resistor_symbols import i2c_netlist_with_device_r_symbol

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_i2c_pullups_to_distinct_rail_families_request_review() -> None:
    policy = policy_without_i2c_map_prompt()
    fault = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
    report = evaluate("synthetic-i2c-rail-review", coach(fault), policy)
    findings = [
        item for item in report.findings if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
    ]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.disposition == "OPEN"
    assert finding.evidence["rail_families"] == ("3v3", "5v")
    assert finding.evidence["pullup_paths"] == (
        "SCL: R3=4700Ω to +3V3 (3v3)",
        "SDA: R1=4700Ω to +3V3 (3v3)",
        "SDA: R2=4700Ω to +5V (5v)",
    )
    assert "do not establish voltage compatibility" in finding.message
    separate_line_fault = evaluate(
        "synthetic-i2c-rail-review",
        coach(i2c_netlist_with_pullup_rails(("+3V3",), ("+5V",))),
        policy,
    )
    assert (
        sum(
            item.rule_id == "bus.i2c_multiple_pullup_rail_families"
            for item in separate_line_fault.findings
        )
        == 1
    )
    dnp_resistor = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
        update={"dnp_components": ("R2",)}
    )
    dnp_report = evaluate("synthetic-i2c-rail-review", coach(dnp_resistor), policy)
    assert "bus.i2c_multiple_pullup_rail_families" not in {
        item.rule_id for item in dnp_report.findings
    }
    dnp_bus = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
        update={"dnp_components": ("U1",)}
    )
    dnp_bus_report = evaluate("synthetic-i2c-rail-review", coach(dnp_bus), policy)
    assert "bus.i2c_multiple_pullup_rail_families" not in {
        item.rule_id for item in dnp_bus_report.findings
    }
    blocked = evaluate(
        "synthetic-i2c-rail-review",
        coach(fault),
        DesignLintPolicy(
            rules=(
                *policy.rules,
                DesignLintRuleOverride(
                    rule_id="bus.i2c_multiple_pullup_rail_families",
                    mode="block",
                    reason="Synthetic project explicitly reviews I2C voltage domains",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    disabled = evaluate(
        "synthetic-i2c-rail-review",
        coach(fault),
        DesignLintPolicy(
            rules=(
                *policy.rules,
                DesignLintRuleOverride(
                    rule_id="bus.i2c_multiple_pullup_rail_families",
                    mode="off",
                    reason="Synthetic fixture disables this review prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    ignored = evaluate(
        "synthetic-i2c-rail-review",
        coach(fault),
        DesignLintPolicy(
            rules=policy.rules,
            ignores=(
                DesignLintIgnore(
                    rule_id="bus.i2c_multiple_pullup_rail_families",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic fixture records an intentional level-domain exception",
                ),
            ),
        ),
    )
    assert ignored.status == "PASS"
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
    )
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.parametrize(
    ("sda_rails", "scl_rails"),
    (
        (("+3V3",), ("+3V3",)),
        (("+3V3", "+3.3V"), ("3V3",)),
        (("+3V3", "+9V_CUSTOM"), ("+3V3",)),
    ),
)
def test_same_family_rails_remain_valid_controls(
    sda_rails: tuple[str, ...],
    scl_rails: tuple[str, ...],
) -> None:
    report = evaluate(
        "synthetic-i2c-rail-review",
        coach(i2c_netlist_with_pullup_rails(sda_rails, scl_rails)),
        policy_without_i2c_map_prompt(),
    )
    assert "bus.i2c_multiple_pullup_rail_families" not in {item.rule_id for item in report.findings}


def test_i2c_pullup_rail_finding_is_order_stable() -> None:
    source = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
    policy = policy_without_i2c_map_prompt()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    original_finding = next(
        item
        for item in evaluate("synthetic-i2c-rail-review", coach(source), policy).findings
        if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
    )
    reordered_finding = next(
        item
        for item in evaluate("synthetic-i2c-rail-review", coach(reordered), policy).findings
        if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
    )
    assert (original_finding.fingerprint, original_finding.evidence) == (
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )


@pytest.mark.design_lint_rule(rule_id="bus.i2c_multiple_pullup_rail_families")
def test_i2c_rail_family_review_recognizes_exact_device_r_symbol_under_non_r_reference() -> None:
    policy = policy_without_i2c_map_prompt()
    fault = i2c_netlist_with_device_r_symbol(rail="+5V", base_pullups=("SCL",))
    report = evaluate("synthetic-i2c-symbol-rail", coach(fault), policy)
    finding = next(
        item
        for item in report.findings
        if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
    )

    assert finding.evidence["rail_families"] == ("3v3", "5v")
    assert "SDA: X1=4700Ω to +5V (5v)" in finding.evidence["pullup_paths"]

    control = i2c_netlist_with_device_r_symbol(rail="+3V3", base_pullups=("SCL",))
    control_report = evaluate("synthetic-i2c-symbol-rail-control", coach(control), policy)
    assert "bus.i2c_multiple_pullup_rail_families" not in {
        item.rule_id for item in control_report.findings
    }
