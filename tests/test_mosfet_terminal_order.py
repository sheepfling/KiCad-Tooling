"""Fault, control, policy, and deterministic-order tests for MOSFET rail lint."""

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
from tests.design_lint_fixtures.mosfet_terminal_order import mosfet_terminal_order_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_terminal_order_on_named_rails"
PROJECT_ID = "synthetic-mosfet-terminal-order"


def lint(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(PROJECT_ID, coach(netlist), policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def review_policy(mode: Literal["review", "block", "off"] = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review MOSFET rails"),)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("channel_type", ("nmos", "pmos"))
def test_reversed_named_rail_order_is_visible_only_after_project_enables_review(
    channel_type: str,
) -> None:
    fault = mosfet_terminal_order_netlist(channel_type=channel_type)

    default = lint(fault)
    enabled = lint(fault, review_policy())
    control = lint(
        mosfet_terminal_order_netlist(channel_type=channel_type, reversed_order=False),
        review_policy(),
    )

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert enabled.status == "REVIEW"
    finding = findings(enabled)[0]
    assert finding.mode == "review"
    assert finding.evidence["channel_type"] == (channel_type,)
    assert finding.evidence["expected_lower_terminal"] == (
        "source" if channel_type == "nmos" else "drain",
    )
    assert finding.evidence["observed_lower_terminal"] == (
        "drain" if channel_type == "nmos" else "source",
    )
    assert finding.evidence["drain_net"] == ("GND" if channel_type == "nmos" else "+5V",)
    assert finding.evidence["source_net"] == ("+5V" if channel_type == "nmos" else "GND",)
    assert control.status == "PASS"
    assert findings(control) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_functions_determine_terminals_independent_of_pin_numbers() -> None:
    observed = mosfet_terminal_order_netlist(
        channel_type="pmos",
        symbol="Transistor_FET:Q_PMOS_SGD",
        pin_numbers={"source": "1", "gate": "2", "drain": "3"},
    )

    finding = findings(lint(observed, review_policy()))[0]

    assert finding.evidence["drain_pin"] == ("Q1.3",)
    assert finding.evidence["source_pin"] == ("Q1.1",)
    assert finding.evidence["expected_lower_terminal"] == ("drain",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_signed_numeric_rails_are_ordered_and_unordered_symbolic_rails_stay_quiet() -> None:
    reversed_numeric = mosfet_terminal_order_netlist(
        channel_type="nmos", drain_net="-3V3", source_net="+3V3"
    )
    symbolic_only = mosfet_terminal_order_netlist(
        channel_type="nmos", drain_net="VNEG_RAIL", source_net="VMAIN_RAIL"
    )
    numeric_finding = findings(lint(reversed_numeric, review_policy()))[0]

    assert numeric_finding.evidence["drain_ordering_value_volts"] == ("-3.3",)
    assert numeric_finding.evidence["source_ordering_value_volts"] == ("3.3",)
    assert findings(lint(symbolic_only, review_policy())) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unsupported_incomplete_dnp_and_ambiguous_devices_are_not_classified() -> None:
    unsupported = mosfet_terminal_order_netlist(symbol="Synthetic:NMOS")
    incomplete = mosfet_terminal_order_netlist(inventory=("1", "2"))
    unpopulated = mosfet_terminal_order_netlist(dnp=("Q1",))
    duplicate_roles = mosfet_terminal_order_netlist(function_overrides={"Q1.2": "D"})
    ambiguous = mosfet_terminal_order_netlist(extra_drain_net="SECOND_DRAIN_ASSIGNMENT")
    unknown_assignment = mosfet_terminal_order_netlist(
        drain_net="UNKNOWN_A", source_net="UNKNOWN_B"
    )

    for observed in (
        unsupported,
        incomplete,
        unpopulated,
        duplicate_roles,
        ambiguous,
        unknown_assignment,
    ):
        assert findings(lint(observed, review_policy())) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_the_review() -> None:
    fault = mosfet_terminal_order_netlist()
    default = lint(fault)
    fingerprint = findings(default)[0].fingerprint
    blocked = lint(fault, review_policy("block"))
    disabled = lint(fault, review_policy("off"))
    ignored = lint(
        fault,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review MOSFET rails",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint,
                    reason="MOSFET reversal reviewed for the circuit topology",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert findings(blocked)[0].mode == "block"
    assert disabled.status == "PASS"
    assert findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_net_mapping_order_and_rail_repair_keep_fingerprints_stable() -> None:
    fault = mosfet_terminal_order_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    enabled = review_policy()
    first, second = findings(lint(fault, enabled))[0], findings(lint(reordered, enabled))[0]
    repaired = findings(lint(mosfet_terminal_order_netlist(reversed_order=False), enabled))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert repaired == ()
