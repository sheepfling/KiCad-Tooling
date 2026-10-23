"""Fault, control, policy, and deterministic-order tests for BJT rail lint."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.bjt_terminal_order import bjt_terminal_order_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.bjt_terminal_order_on_named_rails"
PROJECT_ID = "synthetic-bjt-terminal-order"


def lint(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(PROJECT_ID, coach(netlist), policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def review_policy(mode: Literal["review", "block", "off"] = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review BJT rails"),)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("family", ("npn", "pnp"))
def test_reversed_named_rail_order_is_default_off_and_valid_orientation_is_quiet(
    family: str,
) -> None:
    fault = bjt_terminal_order_netlist(family=family)
    default = lint(fault)
    enabled = lint(fault, review_policy())
    control = lint(bjt_terminal_order_netlist(family=family, reversed_order=False), review_policy())

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert enabled.status == "REVIEW"
    finding = findings(enabled)[0]
    assert finding.mode == "review"
    assert finding.evidence["transistor_family"] == (family,)
    assert finding.evidence["expected_lower_terminal"] == (
        "emitter" if family == "npn" else "collector",
    )
    assert finding.evidence["observed_lower_terminal"] == (
        "collector" if family == "npn" else "emitter",
    )
    assert control.status == "PASS"
    assert findings(control) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_terminal_functions_are_independent_of_pin_numbers_and_signed_rails() -> None:
    observed = bjt_terminal_order_netlist(
        family="pnp",
        symbol="Transistor_BJT:Q_PNP_ECB",
        pin_numbers={"base": "2", "collector": "3", "emitter": "1"},
        collector_net="+3V3",
        emitter_net="-3V3",
    )
    finding = findings(lint(observed, review_policy()))[0]

    assert finding.evidence["collector_pin"] == ("Q1.3",)
    assert finding.evidence["emitter_pin"] == ("Q1.1",)
    assert finding.evidence["expected_lower_terminal"] == ("collector",)
    assert finding.evidence["collector_ordering_value_volts"] == ("3.3",)
    assert finding.evidence["emitter_ordering_value_volts"] == ("-3.3",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unsupported_incomplete_dnp_and_ambiguous_devices_are_not_classified() -> None:
    cases = (
        bjt_terminal_order_netlist(symbol="Synthetic:NPN"),
        bjt_terminal_order_netlist(inventory=("1", "2")),
        bjt_terminal_order_netlist(dnp=("Q1",)),
        bjt_terminal_order_netlist(function_overrides={"Q1.1": "C"}),
        bjt_terminal_order_netlist(extra_collector_net="OTHER_COLLECTOR"),
        bjt_terminal_order_netlist(collector_net="VMAIN", emitter_net="VLOW"),
    )

    for observed in cases:
        assert findings(lint(observed, review_policy())) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_the_review() -> None:
    fault = bjt_terminal_order_netlist()
    fingerprint = findings(lint(fault))[0].fingerprint
    blocked = lint(fault, review_policy("block"))
    disabled = lint(fault, review_policy("off"))
    ignored = lint(
        fault,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Review BJT"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint,
                    reason="Synthetic BJT reversal intentionally reviewed",
                ),
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert findings(blocked)[0].mode == "block"
    assert disabled.status == "PASS"
    assert findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_input_reordering_and_rail_repair_keep_findings_stable() -> None:
    fault = bjt_terminal_order_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    first = findings(lint(fault, review_policy()))[0]
    second = findings(lint(reordered, review_policy()))[0]
    repaired = findings(lint(bjt_terminal_order_netlist(reversed_order=False), review_policy()))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert repaired == ()
