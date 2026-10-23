"""Fault, control, policy, and deterministic-order tests for MOSFET G/S lint."""

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
from tests.design_lint_fixtures.mosfet_gate_source_same_net import mosfet_gate_source_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_gate_source_same_net"
PROJECT_ID = "synthetic-mosfet-gate-source-net"


def lint(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(PROJECT_ID, coach(netlist), policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def review_policy(mode: Literal["review", "block", "off"] = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review MOSFET G/S tie"),)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("symbol", ("Transistor_FET:Q_NMOS_DGS", "Transistor_FET:Q_PMOS_DGS"))
def test_gate_source_same_net_fault_is_opt_in_and_distinct_net_control_is_quiet(
    symbol: str,
) -> None:
    fault = mosfet_gate_source_netlist(symbol=symbol)
    default = lint(fault)
    reviewed = lint(fault, review_policy())
    control = lint(mosfet_gate_source_netlist(symbol=symbol, same_net=False), review_policy())

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert reviewed.status == "REVIEW"
    assert findings(reviewed)[0].mode == "review"
    assert findings(reviewed)[0].evidence["gate_pin"] == ("Q1.2",)
    assert findings(reviewed)[0].evidence["gate_net"] == ("SOURCE",)
    assert findings(reviewed)[0].evidence["source_net"] == ("SOURCE",)
    assert control.status == "PASS"
    assert findings(control) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_functions_map_reordered_mosfet_terminals() -> None:
    observed = mosfet_gate_source_netlist(pin_numbers={"drain": "3", "gate": "1", "source": "2"})

    finding = findings(lint(observed, review_policy()))[0]

    assert finding.evidence["gate_pin"] == ("Q1.1",)
    assert finding.evidence["source_pin"] == ("Q1.2",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unsupported_dnp_incomplete_duplicate_open_and_ambiguous_cases_are_unclassified() -> None:
    cases = (
        mosfet_gate_source_netlist(symbol="Synthetic:NMOS"),
        mosfet_gate_source_netlist(inventory=("1", "2")),
        mosfet_gate_source_netlist(inventory=("1", "2", "2")),
        mosfet_gate_source_netlist(dnp=("Q1",)),
        mosfet_gate_source_netlist(function_overrides={"Q1.2": "D"}),
        mosfet_gate_source_netlist(open_roles=("gate",)),
        mosfet_gate_source_netlist(open_roles=("source",)),
        mosfet_gate_source_netlist(extra_gate_net="SECOND_ASSIGNMENT"),
        mosfet_gate_source_netlist(extra_source_net="SECOND_ASSIGNMENT"),
    )

    assert all(findings(lint(case, review_policy())) == () for case in cases)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_the_review() -> None:
    fault = mosfet_gate_source_netlist()
    fingerprint = findings(lint(fault))[0].fingerprint
    blocked = lint(fault, review_policy("block"))
    disabled = lint(fault, review_policy("off"))
    ignored = lint(
        fault,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Review tie"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint,
                    reason="The MOSFET is intentionally held off by its gate/source tie",
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
def test_repair_and_netlist_order_preserve_deterministic_evidence() -> None:
    fault = mosfet_gate_source_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    enabled = review_policy()
    first, second = findings(lint(fault, enabled))[0], findings(lint(reordered, enabled))[0]
    repaired = findings(lint(mosfet_gate_source_netlist(same_net=False), enabled))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert repaired == ()
