"""Fault, control, policy, and deterministic-order tests for BJT base/collector lint."""

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
from tests.design_lint_fixtures.bjt_collector_emitter_same_net import (
    bjt_base_collector_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.bjt_base_collector_same_net"
PROJECT_ID = "synthetic-bjt-base-collector-same-net"


def lint(
    netlist: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(PROJECT_ID, coach(netlist), policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def review_policy(mode: Literal["review", "block", "off"] = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review a possible diode-connected BJT",
            ),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("family", ("npn", "pnp"))
def test_base_collector_same_net_review_is_opt_in_and_distinct_net_control_is_quiet(
    family: str,
) -> None:
    fault = bjt_base_collector_netlist(family=family)
    default = lint(fault)
    reviewed = lint(fault, review_policy())
    control = lint(bjt_base_collector_netlist(family=family, same_net=False), review_policy())

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert reviewed.status == "REVIEW"
    assert findings(reviewed)[0].mode == "review"
    assert findings(reviewed)[0].evidence["transistor_family"] == (family,)
    assert findings(reviewed)[0].evidence["base_net"] == ("BC_SHARED",)
    assert findings(reviewed)[0].evidence["collector_net"] == ("BC_SHARED",)
    assert control.status == "PASS"
    assert findings(control) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_pin_functions_find_reordered_base_and_collector_roles() -> None:
    observed = bjt_base_collector_netlist(
        family="pnp",
        pin_numbers={"base": "3", "collector": "1", "emitter": "2"},
    )

    finding = findings(lint(observed, review_policy()))[0]

    assert finding.evidence["base_pin"] == ("Q1.3",)
    assert finding.evidence["collector_pin"] == ("Q1.1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unsupported_dnp_incomplete_duplicate_open_and_ambiguous_cases_are_unclassified() -> None:
    cases = (
        bjt_base_collector_netlist(symbol="Synthetic:BJT"),
        bjt_base_collector_netlist(inventory=("1", "2")),
        bjt_base_collector_netlist(dnp=("Q1",)),
        bjt_base_collector_netlist(function_overrides={"Q1.2": "B"}),
        bjt_base_collector_netlist(open_roles=("base",)),
        bjt_base_collector_netlist(open_roles=("collector",)),
        bjt_base_collector_netlist(extra_base_net="SECOND_ASSIGNMENT"),
        bjt_base_collector_netlist(extra_collector_net="SECOND_ASSIGNMENT"),
    )

    assert all(findings(lint(case, review_policy())) == () for case in cases)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_an_intentional_diode_connection() -> None:
    intentional_diode = bjt_base_collector_netlist()
    fingerprint = findings(lint(intentional_diode))[0].fingerprint

    blocked = lint(intentional_diode, review_policy("block"))
    disabled = lint(intentional_diode, review_policy("off"))
    ignored = lint(
        intentional_diode,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Diode-connected current-reference BJT is intentional",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint,
                    reason="This supported transistor is intentionally diode-connected",
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
    fault = bjt_base_collector_netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    enabled = review_policy()

    first, second = findings(lint(fault, enabled))[0], findings(lint(reordered, enabled))[0]
    repaired = findings(lint(bjt_base_collector_netlist(same_net=False), enabled))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert repaired == ()
