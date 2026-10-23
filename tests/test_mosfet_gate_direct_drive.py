"""Fault, control, policy, and deterministic-order tests for MOSFET gate drive."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from tests.design_lint_fixtures.mosfet_gate_direct_drive import netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_gate_direct_drive"
PROJECT_ID = "synthetic-mosfet-gate-direct-drive"


def lint(observed: NetlistContract, mode: str | None = "review") -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(
            ()
            if mode is None
            else (
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode=mode,
                    reason="Review synthetic MOSFET gate drive",
                ),
            )
        )
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=observed,
        netlist_sha256="a" * 64,
    )
    return evaluate(PROJECT_ID, coach, policy)


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_output_capable_pin_directly_sharing_gate_net_is_reviewed() -> None:
    matches = findings(lint(netlist()))
    assert len(matches) == 1
    finding = matches[0]

    assert finding.subject == "Q1.2: MOSFET gate directly shares a net with an output-capable pin"
    assert finding.evidence == {
        "component": ("Q1",),
        "symbol": ("Transistor_FET:Q_NMOS_GDS",),
        "gate_pin": ("Q1.2",),
        "gate_net": ("GATE",),
        "output_pins": ("U1.1",),
        "output_pin_types": ("U1.1=output",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("driver_type", ("power_out", "tri_state", "open_collector"))
def test_other_native_output_capable_pin_types_are_evidence(driver_type: str) -> None:
    finding = findings(lint(netlist(driver_type=driver_type)))[0]

    assert finding.evidence["output_pin_types"] == (f"U1.1={driver_type}",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_series_resistor_separating_driver_and_gate_is_a_control() -> None:
    assert findings(lint(netlist(series_resistor=True))) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "observed",
    (
        pytest.param(netlist(driver_type="input"), id="input-peer"),
        pytest.param(netlist(driver_type="passive"), id="passive-peer"),
        pytest.param(netlist(dnp=("U1",)), id="unfitted-driver"),
        pytest.param(netlist(dnp=("Q1",)), id="unfitted-mosfet"),
        pytest.param(netlist(symbol="Synthetic:Q_NMOS"), id="unsupported-symbol"),
        pytest.param(netlist(inventory=("1", "2")), id="incomplete-inventory"),
        pytest.param(netlist(gate_function="G1"), id="unsupported-gate-function"),
        pytest.param(netlist(driver_also_on_other_net=True), id="ambiguous-driver-assignment"),
    ),
)
def test_unsupported_or_unfitted_topologies_remain_unclassified(
    observed: NetlistContract,
) -> None:
    assert findings(lint(observed)) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_defaults_off_and_policy_can_block_disable_or_ignore() -> None:
    fault = netlist()
    default = lint(fault, mode=None)
    finding = findings(lint(fault))[0]
    blocked = lint(fault, mode="block")
    disabled = lint(fault, mode="off")
    ignored = evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=fault,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Review synthetic MOSFET gate drive",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Driver behavior reviewed for the synthetic control",
                ),
            ),
        ),
    )

    assert default.status == "PASS"
    assert findings(default)[0].disposition == "RULE_OFF"
    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_input_order_does_not_change_fingerprint_or_evidence() -> None:
    observed = netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    first, second = findings(lint(observed))[0], findings(lint(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
